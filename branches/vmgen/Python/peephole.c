/* Peephole optimizations for bytecode compiler. */

#include "Python.h"

#include "Python-ast.h"
#include "node.h"
#include "pyarena.h"
#include "ast.h"
#include "code.h"
#include "compile.h"
#include "instructionsobject.h"
#include "symtable.h"
#include "opcode.h"

static void prepare_peeptable(void);

#define GETOP(inst) PyPInst_GET_OPCODE(&(inst))
#define OP_EQ(inst, EXPECTED) (!(inst).is_arg && GETOP(inst) == EXPECTED)
#define GETARG(arr, i) PyPInst_GET_ARG(&(arr)[(i)+1])
#define UNCONDITIONAL_JUMP(op)	(op==JUMP_ABSOLUTE || op==JUMP_FORWARD)
#define ABSOLUTE_JUMP(op) (op==JUMP_ABSOLUTE || op==CONTINUE_LOOP)
#define GETJUMPTGT(arr, i) (GETARG(arr,i) +	\
			    (ABSOLUTE_JUMP(GETOP((arr)[(i)])) ? 0 : i+2))
#define SETOP(inst, val) PyPInst_SET_OPCODE(&(inst), (val));
#define SETARG(arr, i, val) PyPInst_SET_ARG(&(arr)[(i)+1], (val))
#define ISBASICBLOCK(blocks, start, bytes) \
	(blocks[start]==blocks[start+bytes-1])

static void
set_nops(PyPInst *inststr, Py_ssize_t num_nops) {
	PyPInst *last_inst = inststr + num_nops;
	for (; inststr != last_inst; ++inststr) {
		SETOP(*inststr, NOP);
	}
}

/* Replace LOAD_CONST c1. LOAD_CONST c2 ... LOAD_CONST cn BUILD_TUPLE n
   with	   LOAD_CONST (c1, c2, ... cn).
   The consts table must still be in list form so that the
   new constant (c1, c2, ... cn) can be appended.
   Called with codestr pointing to the first LOAD_CONST.
   Bails out with no change if one or more of the LOAD_CONSTs is missing. 
   Also works for BUILD_LIST when followed by an "in" or "not in" test.
*/
static int
tuple_of_constants(PyPInst *inststr, Py_ssize_t n, PyObject *consts)
{
	PyObject *newconst, *constant;
	Py_ssize_t i, arg, len_consts;

	/* Pre-conditions */
	assert(PyList_CheckExact(consts));
	assert(GETOP(inststr[n*2]) == BUILD_TUPLE ||
	       GETOP(inststr[n*2]) == BUILD_LIST);
	assert(GETARG(inststr, (n*2)) == n);
	for (i=0 ; i<n ; i++)
		assert(GETOP(inststr[i*2]) == LOAD_CONST);

	/* Buildup new tuple of constants */
	newconst = PyTuple_New(n);
	if (newconst == NULL)
		return 0;
	len_consts = PyList_GET_SIZE(consts);
	for (i=0 ; i<n ; i++) {
		arg = GETARG(inststr, (i*2));
		assert(arg < len_consts);
		constant = PyList_GET_ITEM(consts, arg);
		Py_INCREF(constant);
		PyTuple_SET_ITEM(newconst, i, constant);
	}

	/* Append folded constant onto consts */
	if (PyList_Append(consts, newconst)) {
		Py_DECREF(newconst);
		return 0;
	}
	Py_DECREF(newconst);

	/* Write NOPs over old LOAD_CONSTS and
	   add a new LOAD_CONST newconst on top of the BUILD_TUPLE n */
	set_nops(inststr, n*2);
	SETOP(inststr[n*2], LOAD_CONST);
	SETARG(inststr, (n*2), len_consts);
	return 1;
}

/* Replace LOAD_CONST c1. LOAD_CONST c2 BINOP
   with	   LOAD_CONST binop(c1,c2)
   The consts table must still be in list form so that the
   new constant can be appended.
   Called with codestr pointing to the first LOAD_CONST. 
   Abandons the transformation if the folding fails (i.e.  1+'a').  
   If the new constant is a sequence, only folds when the size
   is below a threshold value.	That keeps pyc files from
   becoming large in the presence of code like:	 (None,)*1000.
*/
static int
fold_binops_on_constants(PyPInst *inststr, PyObject *consts)
{
	PyObject *newconst, *v, *w;
	Py_ssize_t len_consts, size;
	int opcode;

	/* Pre-conditions */
	assert(PyList_CheckExact(consts));
	assert(GETOP(inststr[0]) == LOAD_CONST);
	assert(GETOP(inststr[2]) == LOAD_CONST);

	/* Create new constant */
	v = PyList_GET_ITEM(consts, GETARG(inststr, 0));
	w = PyList_GET_ITEM(consts, GETARG(inststr, 2));
	opcode = GETOP(inststr[4]);
	switch (opcode) {
		case BINARY_POWER:
			newconst = PyNumber_Power(v, w, Py_None);
			break;
		case BINARY_MULTIPLY:
			newconst = PyNumber_Multiply(v, w);
			break;
		case BINARY_DIVIDE:
			/* Cannot fold this operation statically since
                           the result can depend on the run-time presence
                           of the -Qnew flag */
			return 0;
		case BINARY_TRUE_DIVIDE:
			newconst = PyNumber_TrueDivide(v, w);
			break;
		case BINARY_FLOOR_DIVIDE:
			newconst = PyNumber_FloorDivide(v, w);
			break;
		case BINARY_MODULO:
			newconst = PyNumber_Remainder(v, w);
			break;
		case BINARY_ADD:
			newconst = PyNumber_Add(v, w);
			break;
		case BINARY_SUBTRACT:
			newconst = PyNumber_Subtract(v, w);
			break;
		case BINARY_SUBSCR:
			newconst = PyObject_GetItem(v, w);
			break;
		case BINARY_LSHIFT:
			newconst = PyNumber_Lshift(v, w);
			break;
		case BINARY_RSHIFT:
			newconst = PyNumber_Rshift(v, w);
			break;
		case BINARY_AND:
			newconst = PyNumber_And(v, w);
			break;
		case BINARY_XOR:
			newconst = PyNumber_Xor(v, w);
			break;
		case BINARY_OR:
			newconst = PyNumber_Or(v, w);
			break;
		default:
			/* Called with an unknown opcode */
			PyErr_Format(PyExc_SystemError,
			     "unexpected binary operation %d on a constant",
				     opcode);
			return 0;
	}
	if (newconst == NULL) {
		PyErr_Clear();
		return 0;
	}
	size = PyObject_Size(newconst);
	if (size == -1)
		PyErr_Clear();
	else if (size > 20) {
		Py_DECREF(newconst);
		return 0;
	}

	/* Append folded constant into consts table */
	len_consts = PyList_GET_SIZE(consts);
	if (PyList_Append(consts, newconst)) {
		Py_DECREF(newconst);
		return 0;
	}
	Py_DECREF(newconst);

	/* Write NOP NOP NOP LOAD_CONST newconst */
	set_nops(inststr, 3);
	SETOP(inststr[3], LOAD_CONST);
	SETARG(inststr, 3, len_consts);
	return 1;
}

static int
fold_unaryops_on_constants(PyPInst *inststr, PyObject *consts)
{
	PyObject *newconst=NULL, *v;
	Py_ssize_t len_consts;
	int opcode;

	/* Pre-conditions */
	assert(PyList_CheckExact(consts));
	assert(GETOP(inststr[0]) == LOAD_CONST);

	/* Create new constant */
	v = PyList_GET_ITEM(consts, GETARG(inststr, 0));
	opcode = GETOP(inststr[2]);
	switch (opcode) {
		case UNARY_NEGATIVE:
			/* Preserve the sign of -0.0 */
			if (PyObject_IsTrue(v) == 1)
				newconst = PyNumber_Negative(v);
			break;
		case UNARY_CONVERT:
			newconst = PyObject_Repr(v);
			break;
		case UNARY_INVERT:
			newconst = PyNumber_Invert(v);
			break;
		default:
			/* Called with an unknown opcode */
			PyErr_Format(PyExc_SystemError,
			     "unexpected unary operation %d on a constant",
				     opcode);
			return 0;
	}
	if (newconst == NULL) {
		PyErr_Clear();
		return 0;
	}

	/* Append folded constant into consts table */
	len_consts = PyList_GET_SIZE(consts);
	if (PyList_Append(consts, newconst)) {
		Py_DECREF(newconst);
		return 0;
	}
	Py_DECREF(newconst);

	/* Write NOP LOAD_CONST newconst */
	SETOP(inststr[0], NOP);
	SETOP(inststr[1], LOAD_CONST);
	SETARG(inststr, 1, len_consts);
	return 1;
}

/* XXX(jyasskin): This currently prevents optimizations that eliminate a
   jump target. Consider whether we want to prevent optimizations that blur
   a line boundary too, and under what circumstances. */
static unsigned int *
markblocks(PyPInst *code, Py_ssize_t len, PyObject *lineno_obj)
{
	unsigned int *blocks = (unsigned int *)PyMem_Malloc(len*sizeof(int));
	int i,j, blockcnt = 0;

	if (blocks == NULL) {
		PyErr_NoMemory();
		return NULL;
	}
	memset(blocks, 0, len*sizeof(int));

	/* Mark labels in the first pass */
	for (i=0 ; i<len ; i++) {
		if (code[i].is_arg)
			continue;
		switch (GETOP(code[i])) {
			case FOR_ITER:
			case JUMP_FORWARD:
			case JUMP_IF_FALSE:
			case JUMP_IF_TRUE:
			case JUMP_ABSOLUTE:
			case CONTINUE_LOOP:
			case SETUP_LOOP:
			case SETUP_EXCEPT:
			case SETUP_FINALLY:
				j = GETJUMPTGT(code, i);
				blocks[j] = 1;
				break;
		}
	}
	if (!Py_OptimizeFlag) {
		/* If -O wasn't passed, we want to avoid combining
		   instructions across line number boundaries.  This
		   both makes code easier to debug and allows users to
		   sensibly set the line number.  In -O mode, we'll
		   disable jumping to avoid crashes. */
		unsigned char *lineno =
				(unsigned char *)PyString_AS_STRING(lineno_obj);
		Py_ssize_t tabsiz = PyString_GET_SIZE(lineno_obj);
		Py_ssize_t code_index = 0;
		Py_ssize_t i;
		for (i=0; i < tabsiz; i+=2) {
			code_index += lineno[i];
			/* This actually makes sense: a trace function
			   can jump to the start of any line, so each
			   line is a basic block. */
			blocks[code_index] = 1;
		}
	}
	/* Build block numbers in the last pass */
	for (i=0 ; i<len ; i++) {
		blockcnt += blocks[i];	/* increment blockcnt over labels */
		blocks[i] = blockcnt;
	}
	return blocks;
}

/* Superinstruction combiner

   - We use a simple, greedy peepholing algorithm for superinstructions
     (taken from the vmgen example code).
   - Vmgen generates the necessary table as an array of tuples of
     instruction indices (known at compile time); we convert this into a
     hash table at runtime.
 */

/* Very simple hash function.  It's the way it is because the arguments are
   contiguous small integers. */
#define HASH_SIZE (1 << 10)
#define HASH(a,b) (((a) ^ ((b) << 5) ^ ((b) >> 5)) & (HASH_SIZE-1))

typedef struct idx_combination {
	int prefix;      /* instruction or superinstruction prefix index */
	int lastprim;    /* most recently added instruction index	*/
	int combination; /* resulting superinstruction index	     */
	struct idx_combination *next;
} IdxCombination;

static IdxCombination peephole_table[] = {
#include "ceval-peephole.i"
};

static IdxCombination *peeptable[HASH_SIZE];

static void
prepare_peeptable()
{
	long i;

	for (i = 0; i < sizeof(peephole_table)/sizeof(peephole_table[0]); i++) {
		IdxCombination *c   = &(peephole_table[i]);
		IdxCombination *p = (IdxCombination*) malloc(sizeof(*p));

		p->prefix      = c->prefix;
		p->lastprim    = c->lastprim;
		p->combination = c->combination;

		long h       = HASH(p->prefix, p->lastprim);
		p->next      = peeptable[h];
		peeptable[h] = p;
	}
}

static int
combine_two(int op1, int op2)
{
	IdxCombination *p;

	for (p = peeptable[HASH(op1, op2)]; p != NULL; p = p->next)
		if (op1 == p->prefix && op2 == p->lastprim)
			return p->combination;

	return -1;
}

/* Combines basic instructions into superinstructions */
static void
combine_to_superinstructions(PyPInst *inststr, Py_ssize_t codelen,
			     unsigned int *blocks)
{
	/* First element of inststr is always an opcode. */
	int working_on = 0;
	int next_arg = 1;
	int i;

	for (i=1; i < codelen; i++) {
		if (inststr[i].is_arg) {
			inststr[next_arg] = inststr[i];
			next_arg++;
		}
		else {
			int super_op = -1;
			/* See ISBASICBLOCK() */
			if (blocks[working_on] == blocks[i]) {
				super_op = combine_two(GETOP(inststr[working_on]),
						       GETOP(inststr[i]));
			}
			if (super_op == -1) {
				/* Start new superinstruction */
				set_nops(inststr + next_arg, i - next_arg);
				working_on = i;
				next_arg = i + 1;
			}
			else {
				/* Continue an existing superinstruction */
				SETOP(inststr[working_on], super_op);
			}
		}
	}
}

/* Takes 'super', an instruction index, and fills the component
   primitive instructions into the 'prims' array, which must hold at
   least 'prims_len' elements.  Returns the number of primitive
   instructions now in the array.  The instructions are returned in
   reverse order, so if _PyCode_UncombineSuperInstruction returns 3,
   prims[2] will hold the first component instruction, prims[1] will
   hold the second, and prims[0] will hold the third.  Returns -1 if
   prims_len is too small. */
int _PyCode_UncombineSuperInstruction(int super, int *prims, int prims_len)
{
	int num_prims = 0;
	const int num_supers =
		sizeof(peephole_table) / sizeof(peephole_table[0]);
	int super_found = true;
	while (super_found) {
		int i;
		super_found = false;
		for (i = 0; i < num_supers; i++) {
			if (peephole_table[i].combination == super) {
				if (num_prims >= prims_len) {
					return -1;
				}
				super = peephole_table[i].prefix;
				prims[num_prims++] = peephole_table[i].lastprim;
				super_found = true;
				break;
			}
		}
	}
	if (num_prims >= prims_len) {
		return -1;
	}
	prims[num_prims++] = super;
	return num_prims;
}

/* Perform basic peephole optimizations to components of a code object.
   The consts object should still be in list form to allow new constants 
   to be appended.

   To keep the optimizer simple, it bails out (does nothing) for code that
   has a length over 32,700.  That allows us to avoid overflow and sign
   issues.  Likewise, it bails when the lineno table has complex encoding
   for gaps >= 255.

   Optimizations are restricted to simple transformations occuring within a
   single basic block.	All transformations keep the code size the same or 
   smaller.  For those that reduce size, the gaps are initially filled with 
   NOPs.  Later those NOPs are removed and the jump addresses retargeted in 
   a single pass.  Line numbering is adjusted accordingly. */

PyObject *
PyCode_Optimize(PyObject *code, PyObject* consts, PyObject *names,
                PyObject *lineno_obj)
{
	Py_ssize_t i, j, codelen;
	int nops, h;
	int tgt, tgttgt, opcode;
	PyInstructionsObject *modcode = NULL;
	PyPInst *inststr;
	unsigned char *lineno;
	int *addrmap = NULL;
	int new_code, cum_orig_code_offset, last_code, tabsiz;
	int cumlc=0, lastlc=0;	/* Count runs of consecutive LOAD_CONSTs */
	unsigned int *blocks = NULL;
	char *name;
	static int init = 1;

	if (init) {
		prepare_peeptable();
		init = 0;
	}

	/* Bail out if an exception is set */
	if (PyErr_Occurred())
		goto exitUnchanged;

	/* Bypass optimization when the lineno table is too complex */
	assert(PyString_Check(lineno_obj));
	lineno = (unsigned char*)PyString_AS_STRING(lineno_obj);
	tabsiz = PyString_GET_SIZE(lineno_obj);
	if (memchr(lineno, 255, tabsiz) != NULL)
		goto exitUnchanged;

	/* Avoid situations where jump retargeting could overflow */
	codelen = Py_SIZE(code);
	if (codelen > 32700)
		goto exitUnchanged;

	/* Make a modifiable copy of the code string */
	modcode = _PyInstructions_New(codelen);
	if (modcode == NULL)
		goto exitUnchanged;
	inststr = modcode->inst;
	memcpy(inststr, ((PyInstructionsObject *)code)->inst,
	       codelen * sizeof(modcode->inst[0]));

	/* Verify that RETURN_VALUE terminates the codestring.	This allows
	   the various transformation patterns to look ahead several
	   instructions without additional checks to make sure they are not
	   looking beyond the end of the code string.
	*/
	if (!OP_EQ(inststr[codelen-1], RETURN_VALUE))
		goto exitUnchanged;

	/* Mapping to new jump targets after NOPs are removed */
	addrmap = (int *)PyMem_Malloc(codelen * sizeof(int));
	if (addrmap == NULL)
		goto exitUnchanged;

	blocks = markblocks(inststr, Py_SIZE(modcode), lineno_obj);
	if (blocks == NULL)
		goto exitUnchanged;
	assert(PyList_Check(consts));

	for (i=0 ; i<codelen ; i++) {
		if (inststr[i].is_arg)
			continue;
		opcode = GETOP(inststr[i]);

		lastlc = cumlc;
		cumlc = 0;

		switch (opcode) {

			/* Replace UNARY_NOT JUMP_IF_FALSE POP_TOP with 
			   with	   JUMP_IF_TRUE POP_TOP */
			case UNARY_NOT:
				if (GETOP(inststr[i+1]) != JUMP_IF_FALSE  ||
				    GETOP(inststr[i+3]) != POP_TOP  ||
				    !ISBASICBLOCK(blocks,i,4))
					continue;
				tgt = GETJUMPTGT(inststr, (i+1));
				if (GETOP(inststr[tgt]) != POP_TOP)
					continue;
				j = GETARG(inststr, i+1) + 1;
				SETOP(inststr[i], JUMP_IF_TRUE);
				SETARG(inststr, i, j);
				SETOP(inststr[i+2], POP_TOP);
				SETOP(inststr[i+3], NOP);
				break;

				/* not a is b -->  a is not b
				   not a in b -->  a not in b
				   not a is not b -->  a is b
				   not a not in b -->  a in b
				*/
			case COMPARE_OP:
				j = GETARG(inststr, i);
				if (j < 6  ||  j > 9  ||
				    GETOP(inststr[i+2]) != UNARY_NOT  ||
				    !ISBASICBLOCK(blocks,i,3))
					continue;
				SETARG(inststr, i, (j^1));
				SETOP(inststr[i+2], NOP);
				break;

				/* Replace LOAD_GLOBAL/LOAD_NAME None
                                   with LOAD_CONST None */
			case LOAD_NAME:
			case LOAD_GLOBAL:
				j = GETARG(inststr, i);
				name = PyString_AsString(PyTuple_GET_ITEM(names, j));
				if (name == NULL  ||  strcmp(name, "None") != 0)
					continue;
				for (j=0 ; j < PyList_GET_SIZE(consts) ; j++) {
					if (PyList_GET_ITEM(consts, j) == Py_None)
						break;
				}
				if (j == PyList_GET_SIZE(consts)) {
					if (PyList_Append(consts, Py_None) == -1)
					        goto exitUnchanged;                                        
				}
				assert(PyList_GET_ITEM(consts, j) == Py_None);
				SETOP(inststr[i], LOAD_CONST);
				SETARG(inststr, i, j);
				cumlc = lastlc + 1;
				break;

				/* Skip over LOAD_CONST trueconst
                                   JUMP_IF_FALSE xx  POP_TOP */
			case LOAD_CONST:
				cumlc = lastlc + 1;
				j = GETARG(inststr, i);
				if (GETOP(inststr[i+2]) != JUMP_IF_FALSE  ||
				    GETOP(inststr[i+4]) != POP_TOP  ||
				    !ISBASICBLOCK(blocks,i,5)  ||
				    !PyObject_IsTrue(PyList_GET_ITEM(consts, j)))
					continue;
				set_nops(inststr+i, 5);
				cumlc = 0;
				break;

				/* Try to fold tuples of constants (includes a case for lists
				   which are only used for "in" and "not in" tests).
				   Skip over BUILD_SEQN 1 UNPACK_SEQN 1.
				   Replace BUILD_SEQN 2 UNPACK_SEQN 2 with ROT2.
				   Replace BUILD_SEQN 3 UNPACK_SEQN 3 with ROT3 ROT2. */
			case BUILD_TUPLE:
			case BUILD_LIST:
				j = GETARG(inststr, i);
				h = i - 2 * j;
				if (h >= 0  &&
				    j <= lastlc	 &&
				    ((opcode == BUILD_TUPLE && 
				      ISBASICBLOCK(blocks, h, 2*(j+1))) ||
				     (opcode == BUILD_LIST && 
				      GETOP(inststr[i+2])==COMPARE_OP && 
				      ISBASICBLOCK(blocks, h, 2*(j+2)) &&
				      (GETARG(inststr,i+2)==6 ||
				       GETARG(inststr,i+2)==7))) &&
				    tuple_of_constants(&inststr[h], j, consts)) {
					assert(GETOP(inststr[i]) == LOAD_CONST);
					cumlc = 1;
					break;
				}
				if (GETOP(inststr[i+2]) != UNPACK_SEQUENCE  ||
				    !ISBASICBLOCK(blocks,i,4) ||
				    j != GETARG(inststr, i+2))
					continue;
				if (j == 1) {
					set_nops(inststr+i, 4);
				} else if (j == 2) {
					SETOP(inststr[i], ROT_TWO);
					set_nops(inststr+i+1, 3);
				} else if (j == 3) {
					SETOP(inststr[i], ROT_THREE);
					SETOP(inststr[i+1], ROT_TWO);
					set_nops(inststr+i+2, 2);
				}
				break;

				/* Fold binary ops on constants.
				   LOAD_CONST c1 LOAD_CONST c2 BINOP -->  LOAD_CONST binop(c1,c2) */
			case BINARY_POWER:
			case BINARY_MULTIPLY:
			case BINARY_TRUE_DIVIDE:
			case BINARY_FLOOR_DIVIDE:
			case BINARY_MODULO:
			case BINARY_ADD:
			case BINARY_SUBTRACT:
			case BINARY_SUBSCR:
			case BINARY_LSHIFT:
			case BINARY_RSHIFT:
			case BINARY_AND:
			case BINARY_XOR:
			case BINARY_OR:
				if (lastlc >= 2	 &&
				    ISBASICBLOCK(blocks, i-4, 5)  &&
				    fold_binops_on_constants(&inststr[i-4], consts)) {
					i -= 1;
					assert(GETOP(inststr[i]) == LOAD_CONST);
					cumlc = 1;
				}
				break;

				/* Fold unary ops on constants.
				   LOAD_CONST c1  UNARY_OP -->	LOAD_CONST unary_op(c) */
			case UNARY_NEGATIVE:
			case UNARY_CONVERT:
			case UNARY_INVERT:
				if (lastlc >= 1	 &&
				    ISBASICBLOCK(blocks, i-2, 3)  &&
				    fold_unaryops_on_constants(&inststr[i-2], consts))	{
					i -= 1;
					assert(GETOP(inststr[i]) == LOAD_CONST);
					cumlc = 1;
				}
				break;

				/* Simplify conditional jump to conditional jump where the
				   result of the first test implies the success of a similar
				   test or the failure of the opposite test.
				   Arises in code like:
				   "if a and b:"
				   "if a or b:"
				   "a and b or c"
				   "(a and b) and c"
				   x:JUMP_IF_FALSE y   y:JUMP_IF_FALSE z  -->  x:JUMP_IF_FALSE z
				   x:JUMP_IF_FALSE y   y:JUMP_IF_TRUE z	 -->  x:JUMP_IF_FALSE y+2
				   where y+2 is the instruction following the second test.
				*/
			case JUMP_IF_FALSE:
			case JUMP_IF_TRUE:
				tgt = GETJUMPTGT(inststr, i);
				j = GETOP(inststr[tgt]);
				if (j == JUMP_IF_FALSE	||  j == JUMP_IF_TRUE) {
					if (j == opcode) {
						tgttgt = GETJUMPTGT(inststr, tgt) - i - 2;
						SETARG(inststr, i, tgttgt);
					} else {
						tgt -= i;
						SETARG(inststr, i, tgt);
					}
					break;
				}
				/* Intentional fallthrough */  

				/* Replace jumps to unconditional jumps */
			case FOR_ITER:
			case JUMP_FORWARD:
			case JUMP_ABSOLUTE:
			case CONTINUE_LOOP:
			case SETUP_LOOP:
			case SETUP_EXCEPT:
			case SETUP_FINALLY:
				tgt = GETJUMPTGT(inststr, i);
				/* Replace JUMP_* to a RETURN into just a RETURN */
				if (UNCONDITIONAL_JUMP(opcode) &&
				    GETOP(inststr[tgt]) == RETURN_VALUE) {
					SETOP(inststr[i], RETURN_VALUE);
					memset(inststr+i+1, NOP, 1);
					continue;
				}
				if (!UNCONDITIONAL_JUMP(GETOP(inststr[tgt])))
					continue;
				tgttgt = GETJUMPTGT(inststr, tgt);
				if (opcode == JUMP_FORWARD) /* JMP_ABS can go backwards */
					opcode = JUMP_ABSOLUTE;
				if (!ABSOLUTE_JUMP(opcode))
					tgttgt -= i + 2;     /* Calc relative jump addr */
				if (tgttgt < 0)		  /* No backward relative jumps */
					continue;
				SETOP(inststr[i], opcode);
				SETARG(inststr, i, tgttgt);
				break;

				/* Replace RETURN LOAD_CONST None RETURN with just RETURN */
				/* Remove unreachable JUMPs after RETURN */
			case RETURN_VALUE:
				if (i+3 >= codelen)
					continue;
				if (OP_EQ(inststr[i+3], RETURN_VALUE) &&
				    ISBASICBLOCK(blocks,i,4))
					set_nops(inststr+i+1, 3);
				else if (UNCONDITIONAL_JUMP(GETOP(inststr[i+1])) &&
				         ISBASICBLOCK(blocks,i,3))
					set_nops(inststr+i+1, 2);
				break;
		}
	}

	combine_to_superinstructions(inststr, codelen, blocks);

	last_code = 0;
	/* Fixup linenotab */
	for (i=0, nops=0 ; i<codelen ; i++) {
		if (inststr[i].is_arg) {
			/* Line numbers can point to code that has been
			   turned into an argument.  Resolve them to the
			   next earlier opcode. */
			addrmap[i] = last_code;
			continue;
		}
		addrmap[i] = last_code = i - nops;
		if (GETOP(inststr[i]) == NOP)
			nops++;
	}
	cum_orig_code_offset = 0;
	last_code = 0;
	for (i=0 ; i < tabsiz ; i+=2) {
		cum_orig_code_offset += lineno[i];
		new_code = addrmap[cum_orig_code_offset];
		/* We checked above that no two lines are more than 255 code
		   elements apart.  Since the peephole optimizer only
		   reduces the size of the bytecode, we know that they're
		   still less than 255 apart.  */
		assert (last_code <= new_code && new_code - last_code < 255);
		lineno[i] =((unsigned char)(new_code - last_code));
		last_code = new_code;
	}

	/* Remove NOPs and fixup jump targets */
	for (i=0, h=0 ; i<codelen ; ) {
		opcode = GETOP(inststr[i]);
		switch (opcode) {
			case NOP:
				i++;
				continue;

			case JUMP_ABSOLUTE:
			case POP_JUMP_ABSOLUTE:
			case CONTINUE_LOOP:
				j = addrmap[GETARG(inststr, i)];
				SETARG(inststr, i, j);
				break;

			case FOR_ITER:
			case JUMP_FORWARD:
			case JUMP_IF_FALSE:
			case JUMP_IF_TRUE:
			case SETUP_LOOP:
			case SETUP_EXCEPT:
			case SETUP_FINALLY:
				j = addrmap[GETARG(inststr, i) + i + 2] - addrmap[i] - 2;
				SETARG(inststr, i, j);
				break;
		}
		inststr[h++] = inststr[i++];
		while (i < codelen && inststr[i].is_arg)
			inststr[h++] = inststr[i++];
	}
	assert(h + nops == codelen);

	if (_PyInstructions_Resize(&modcode, h) < 0)
		goto exitUnchanged;
	PyMem_Free(addrmap);
	PyMem_Free(blocks);
	return (PyObject *)modcode;

 exitUnchanged:
	if (blocks != NULL)
		PyMem_Free(blocks);
	if (addrmap != NULL)
		PyMem_Free(addrmap);
	Py_XDECREF(modcode);

	Py_INCREF(code);
	return code;
}
