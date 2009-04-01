# Tests for our minimal LLVM wrappers

from test.test_support import run_unittest, findfile
import unittest
import _llvm
import __future__


class LlvmTests(unittest.TestCase):
    def setUp(self):
        self.bitcode = open(findfile('arithmetic.bc')).read()
        self.module = _llvm._module.from_bitcode('arithmetic.bc', self.bitcode)

    def test_bitcode_to_assembly(self):
        self.assertEquals(str(self.module), """\
; ModuleID = 'arithmetic.bc'

define i32 @mul_add(i32 %x, i32 %y, i32 %z) {
entry:
	%tmp = mul i32 %x, %y		; <i32> [#uses=1]
	%tmp2 = add i32 %tmp, %z		; <i32> [#uses=1]
	ret i32 %tmp2
}

define i32 @shl_add(i32 %x, i32 %y, i32 %z) {
entry:
	%tmp = shl i32 %x, %y		; <i32> [#uses=1]
	%tmp2 = add i32 %tmp, %z		; <i32> [#uses=1]
	ret i32 %tmp2
}
""")

    def test_module_repr(self):
        # The above string isn't suitable to construct a new module,
        # so it shouldn't be the repr.
        self.assertNotEquals(str(self.module), repr(self.module))

    def test_iter_to_functions(self):
        functions = list(self.module.functions())
        self.assertEquals(2, len(functions))
        self.assertEquals(str(functions[0]), """\

define i32 @mul_add(i32 %x, i32 %y, i32 %z) {
entry:
	%tmp = mul i32 %x, %y		; <i32> [#uses=1]
	%tmp2 = add i32 %tmp, %z		; <i32> [#uses=1]
	ret i32 %tmp2
}
""")
        self.assertEquals(str(functions[1]), """\

define i32 @shl_add(i32 %x, i32 %y, i32 %z) {
entry:
	%tmp = shl i32 %x, %y		; <i32> [#uses=1]
	%tmp2 = add i32 %tmp, %z		; <i32> [#uses=1]
	ret i32 %tmp2
}
""")

    def test_function_repr(self):
        # The above strings aren't suitable to construct a new
        # function, so they shouldn't be the reprs.
        function = self.module.functions().next()
        self.assertNotEquals(str(function), repr(function))

    def test_uncreatable(self):
        # Modules and functions can only be created by their static factories.
        self.assertRaises(TypeError, _llvm._module)
        self.assertRaises(TypeError, _llvm._function)

    def test_module_data(self):
        # Certain types and constants get defined at the module level,
        # uniformly for any function.
        namespace = {}
        exec "def foo(): pass" in namespace
        disassembly = str(namespace['foo'].__code__.co_llvm.module)
        module_data = disassembly[:disassembly.find(
                'define %__pyobject* @"<module>"')]
        self.assertEquals(module_data,
                          """\
; ModuleID = '<string>'
	%__function_type = type %__pyobject* (%__pyframeobject*)
	%__pycodeobject = type { %__pyobject, i32, i32, i32, i32, %__pyobject*, %__pyobject*, %__pyobject*, %__pyobject*, %__pyobject*, %__pyobject*, i8*, %__pyobject*, %__pyobject*, i32, %__pyobject*, i8*, %__pyobject* }
	%__pyframeobject = type { %__pyobject, i32, %__pyobject*, %__pycodeobject*, %__pyobject*, %__pyobject*, %__pyobject*, %__pyobject**, %__pyobject**, %__pyobject*, %__pyobject*, %__pyobject*, %__pyobject*, i8*, i32, i32, i32, [20 x { i32, i32, i32 }], [0 x %__pyobject*] }
	%__pyobject = type { %__pyobject*, %__pyobject*, i32, %__pyobject* }
	%__pytupleobject = type { %__pyobject, i32, [0 x %__pyobject*] }
@_Py_RefTotal = external global i32		; <i32*> [#uses=6]

""")

    def test_simple_function_definition(self):
        namespace = {}
        exec "def foo(): return" in namespace
        self.assertEquals(str(namespace['foo'].__code__.co_llvm),
                          """\

define %__pyobject* @foo(%__pyframeobject* %frame) {
entry:
	%0 = getelementptr %__pyframeobject* %frame, i32 0, i32 8		; <%__pyobject***> [#uses=1]
	%initial_stack_pointer = load %__pyobject*** %0		; <%__pyobject**> [#uses=1]
	%1 = getelementptr %__pyframeobject* %frame, i32 0, i32 3		; <%__pycodeobject**> [#uses=1]
	%co = load %__pycodeobject** %1		; <%__pycodeobject*> [#uses=1]
	%2 = getelementptr %__pycodeobject* %co, i32 0, i32 6		; <%__pyobject**> [#uses=1]
	%3 = load %__pyobject** %2		; <%__pyobject*> [#uses=1]
	%consts = getelementptr %__pyobject* %3, i32 1, i32 1		; <%__pyobject**> [#uses=1]
	%4 = load %__pyobject** %consts		; <%__pyobject*> [#uses=3]
	%5 = load i32* @_Py_RefTotal		; <i32> [#uses=1]
	%6 = add i32 %5, 1		; <i32> [#uses=1]
	store i32 %6, i32* @_Py_RefTotal
	%7 = getelementptr %__pyobject* %4, i32 0, i32 2		; <i32*> [#uses=2]
	%8 = load i32* %7		; <i32> [#uses=1]
	%9 = add i32 %8, 1		; <i32> [#uses=1]
	store i32 %9, i32* %7
	store %__pyobject* %4, %__pyobject** %initial_stack_pointer
	ret %__pyobject* %4
}
""")

    def test_run_simple_function(self):
        def foo():
            pass
        foo.__code__.__use_llvm__ = True
        self.assertEquals(None, foo())

    def test_return_arg(self):
        def foo(a):
            return a
        foo.__code__.__use_llvm__ = True
        self.assertEquals(3, foo(3))
        self.assertEquals("Hello", foo("Hello"))

    def test_unbound_local(self):
        def foo():
            a = a
        foo.__code__.__use_llvm__ = True
        try:
            foo()
        except UnboundLocalError as e:
            self.assertEquals(
                str(e), "local variable 'a' referenced before assignment")
        else:
            self.fail("Expected UnboundLocalError")

    def test_assign(self):
        def foo(a):
            b = a
            return b
        foo.__code__.__use_llvm__ = True
        self.assertEquals(3, foo(3))
        self.assertEquals("Hello", foo("Hello"))

    def test_raising_getiter(self):
        class RaisingIter(object):
            def __iter__(self):
                raise RuntimeError
        def loop(range):
            for i in range:
                pass
        loop.__code__.__use_llvm__ = True
        self.assertRaises(RuntimeError, loop, RaisingIter())

    def test_raising_next(self):
        class RaisingNext(object):
            def __iter__(self):
                return self
            def next(self):
                raise RuntimeError
        def loop(range):
            for i in range:
                pass
        loop.__code__.__use_llvm__ = True
        self.assertRaises(RuntimeError, loop, RaisingNext())

    def test_loop(self):
        def loop(range):
            for i in range:
                pass
        loop.__code__.__use_llvm__ = True
        r = iter(range(12))
        self.assertEquals(None, loop(r))
        self.assertRaises(StopIteration, next, r)

    def test_subscr(self):
        def subscr(x):
            x[0] = x[1], x[-1]
            x[1] += 10
            x[-1] = 4
            del x[3]
            del x[-2]
            return x
        non_llvm = subscr([1, 2, 3, 4, 5])
        subscr.__code__.__use_llvm__ = True
        self.assertEquals(subscr([1, 2, 3, 4, 5]), non_llvm)
        
    def test_listcomp(self):
        def listcomp(x):
            return [ item+1 for item in x ]
        non_llvm = listcomp([1, 2, 3])
        listcomp.__code__.__use_llvm__ = True
        self.assertEquals(listcomp([1, 2, 3]), non_llvm)
        
        def listcomp(x):
            return [ [ i + j for j in x ] for i in x ]
        non_llvm = listcomp([1, 2, 3])
        listcomp.__code__.__use_llvm__ = True
        self.assertEquals(listcomp([1, 2, 3]), non_llvm)

        def listcomp(x):
            return [ [ i + j for j in () ] for i in x ]
        non_llvm = listcomp([1, 2, 3])
        listcomp.__code__.__use_llvm__ = True
        self.assertEquals(listcomp([1, 2, 3]), non_llvm)

    def test_literals(self):
        def lits(x):
            return (1, x, 3)
        lits.__code__.__use_llvm__ = True
        self.assertEquals(lits(2), (1, 2, 3))
        def lits(x):
            return (1, x, (3, 4, x), 1)
        lits.__code__.__use_llvm__ = True
        self.assertEquals(lits(2), (1, 2, (3, 4, 2), 1))
        def lits(x):
            return [1, x, 3]
        lits.__code__.__use_llvm__ = True
        self.assertEquals(lits(2), [1, 2, 3])
        def lits(x):
            return [1, x, [3, 2], 1]
        lits.__code__.__use_llvm__ = True
        self.assertEquals(lits(2), [1, 2, [3, 2], 1])
        def lits(x):
            return {1: x, 3: 4}
        lits.__code__.__use_llvm__ = True
        self.assertEquals(lits(2), {1: 2, 3: 4})
        def lits(x):
            return {(1, x): {3: x}, x: 1}
        lits.__code__.__use_llvm__ = True
        self.assertEquals(lits(2), {(1, 2): {3: 2}, 2: 1})
        def lits(x):
            return (1, x, 3, (3, 4), [3, x, 1], {1: x, 3: 4 })
        lits.__code__.__use_llvm__ = True
        self.assertEquals(lits(2), (1, 2, 3, (3, 4), [3, 2, 1], {1: 2, 3: 4}))

    def test_opcodes(self):
        # Test some specific opcodes
        def pop_top(x):
            x
            x
            x
            
        pop_top.__code__.__use_llvm__ = True
        pop_top('pop me')


# dont_inherit will unfortunately not turn off true division when
# running with -Qnew, so we can't test classic division in
# test_basic_arithmetic when running with -Qnew.
# Make sure we aren't running with -Qnew. A __future__
# statement in this module should not affect things.
_co = compile('1 / 2', 'truediv_check', 'eval',
             flags=0, dont_inherit=True)
assert eval(_co) == 0, "Do not run test_llvm with -Qnew"
del _co

class OpRecorder(object):
    # regular binary arithmetic operations
    def __init__(self):
        self.ops = []
    def __add__(self, other):
        self.ops.append('add')
        return 1
    def __sub__(self, other):
        self.ops.append('sub')
        return 2
    def __mul__(self, other):
        self.ops.append('mul')
        return 3
    def __div__(self, other):
        self.ops.append('div')
        return 4
    def __truediv__(self, other):
        self.ops.append('truediv')
        return 5
    def __floordiv__(self, other):
        self.ops.append('floordiv')
        return 6
    def __mod__(self, other):
        self.ops.append('mod')
        return 7
    def __pow__(self, other):
        self.ops.append('pow')
        return 8
    def __lshift__(self, other):
        self.ops.append('lshift')
        return 9
    def __rshift__(self, other):
        self.ops.append('rshift')
        return 10
    def __and__(self, other):
        self.ops.append('and')
        return 11
    def __or__(self, other):
        self.ops.append('or')
        return 12
    def __xor__(self, other):
        self.ops.append('xor')
        return 13

    # Unary operations
    def __nonzero__(self):
        self.ops.append('nonzero')
        return False
    def __invert__(self):
        self.ops.append('invert')
        return 14
    def __pos__(self):
        self.ops.append('pos')
        return 15
    def __neg__(self):
        self.ops.append('neg')
        return 16
    def __repr__(self):
        self.ops.append('repr')
        return '<OpRecorder 17>'
        
    # right-hand binary arithmetic operations
    def __radd__(self, other):
        self.ops.append('radd')
        return 101
    def __rsub__(self, other):
        self.ops.append('rsub')
        return 102
    def __rmul__(self, other):
        self.ops.append('rmul')
        return 103
    def __rdiv__(self, other):
        self.ops.append('rdiv')
        return 104
    def __rtruediv__(self, other):
        self.ops.append('rtruediv')
        return 105
    def __rfloordiv__(self, other):
        self.ops.append('rfloordiv')
        return 106
    def __rmod__(self, other):
        self.ops.append('rmod')
        return 107
    def __rpow__(self, other):
        self.ops.append('rpow')
        return 108
    def __rlshift__(self, other):
        self.ops.append('rlshift')
        return 109
    def __rrshift__(self, other):
        self.ops.append('rrshift')
        return 110
    def __rand__(self, other):
        self.ops.append('rand')
        return 111
    def __ror__(self, other):
        self.ops.append('ror')
        return 112
    def __rxor__(self, other):
        self.ops.append('rxor')
        return 113

    # In-place binary arithmetic operations
    def __iadd__(self, other):
        self.ops.append('iadd')
        return 1001
    def __isub__(self, other):
        self.ops.append('isub')
        return 1002
    def __imul__(self, other):
        self.ops.append('imul')
        return 1003
    def __idiv__(self, other):
        self.ops.append('idiv')
        return 1004
    def __itruediv__(self, other):
        self.ops.append('itruediv')
        return 1005
    def __ifloordiv__(self, other):
        self.ops.append('ifloordiv')
        return 1006
    def __imod__(self, other):
        self.ops.append('imod')
        return 1007
    def __ipow__(self, other):
        self.ops.append('ipow')
        return 1008
    def __ilshift__(self, other):
        self.ops.append('ilshift')
        return 1009
    def __irshift__(self, other):
        self.ops.append('irshift')
        return 1010
    def __iand__(self, other):
        self.ops.append('iand')
        return 1011
    def __ior__(self, other):
        self.ops.append('ior')
        return 1012
    def __ixor__(self, other):
        self.ops.append('ixor')
        return 1013

class OperatorTests(unittest.TestCase):
    def test_basic_arithmetic(self):
        operators = ('+', '-', '*', '/', '//', '%', '**',
                     '<<', '>>', '&', '|', '^')
        parts = []
        for op in operators:
            parts.extend([
                'results["regular %s"] = x %s 1' % (op, op),
                'results["reverse %s"] = 1 %s x' % (op, op),
                'y = x;y %s= 1; results["in-place %s"] = y' % (op, op),
            ])
        testcode = '\n'.join(['def test(x, results):',
                              '  ' + '\n  '.join(parts)])
        co = compile(testcode, 'basic_arithmetic', 'exec',
                     flags=0, dont_inherit=True)
        namespace = {}
        exec co in namespace
        testfunc = namespace['test']

        non_llvm_results = {}
        non_llvm_recorder = OpRecorder()
        testfunc(non_llvm_recorder, non_llvm_results)
        self.assertEquals(len(non_llvm_recorder.ops), len(operators) * 3)
        self.assertEquals(len(non_llvm_results), len(operators) * 3)
        self.assertEquals(len(set(non_llvm_results.values())),
                          len(non_llvm_results))
        

        testfunc.__code__.__use_llvm__ = True
        llvm_results = {}
        llvm_recorder = OpRecorder()
        testfunc(llvm_recorder, llvm_results)

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_recorder.ops, llvm_recorder.ops)

    def test_truediv(self):
        truedivcode = '''def test(x, results):
                             results["regular div"] = x / 1
                             results["reverse div"] = 1 / x
                             x /= 1; results["in-place div"] = x'''
        co = compile(truedivcode, 'truediv_arithmetic', 'exec',
                     flags=__future__.division.compiler_flag,
                     dont_inherit=True)
        namespace = {}
        exec co in namespace
        testfunc = namespace['test']

        non_llvm_results = {}
        non_llvm_recorder = OpRecorder()
        testfunc(non_llvm_recorder, non_llvm_results)
        self.assertEquals(len(non_llvm_recorder.ops), 3)
        self.assertEquals(len(non_llvm_results), 3)
        self.assertEquals(len(set(non_llvm_results.values())), 3)

        testfunc.__code__.__use_llvm__ = True
        llvm_results = {}
        llvm_recorder = OpRecorder()
        testfunc(llvm_recorder, llvm_results)

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_recorder.ops, llvm_recorder.ops)
                             
    def test_unary(self):
        def testfunc(x, results):
            results['not'] = not x
            results['invert'] = ~x
            results['pos'] = +x
            results['neg'] = -x
            results['convert'] = `x`

        non_llvm_results = {}
        non_llvm_recorder = OpRecorder()
        testfunc(non_llvm_recorder, non_llvm_results)
        self.assertEquals(len(non_llvm_recorder.ops), 5)
        self.assertEquals(len(non_llvm_results), 5)
        self.assertEquals(len(set(non_llvm_results.values())), 5)

        testfunc.__code__.__use_llvm__ = True
        llvm_results = {}
        llvm_recorder = OpRecorder()
        testfunc(llvm_recorder, llvm_results)

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_recorder.ops, llvm_recorder.ops)

class OpExc(Exception):
    def __cmp__(self, other):
        return cmp(self.args, other.args)
    def __hash__(self):
        return hash(self.args)

class OpRaiser(object):
    # regular binar arithmetic operations
    def __init__(self):
        self.ops = []
    def __add__(self, other):
        self.ops.append('add')
        raise OpExc(1)
    def __sub__(self, other):
        self.ops.append('sub')
        raise OpExc(2)
    def __mul__(self, other):
        self.ops.append('mul')
        raise OpExc(3)
    def __div__(self, other):
        self.ops.append('div')
        raise OpExc(4)
    def __truediv__(self, other):
        self.ops.append('truediv')
        raise OpExc(5)
    def __floordiv__(self, other):
        self.ops.append('floordiv')
        raise OpExc(6)
    def __mod__(self, other):
        self.ops.append('mod')
        raise OpExc(7)
    def __pow__(self, other):
        self.ops.append('pow')
        raise OpExc(8)
    def __lshift__(self, other):
        self.ops.append('lshift')
        raise OpExc(9)
    def __rshift__(self, other):
        self.ops.append('rshift')
        raise OpExc(10)
    def __and__(self, other):
        self.ops.append('and')
        raise OpExc(11)
    def __or__(self, other):
        self.ops.append('or')
        raise OpExc(12)
    def __xor__(self, other):
        self.ops.append('xor')
        raise OpExc(13)

    # Unary operations
    def __nonzero__(self):
        self.ops.append('nonzero')
        raise OpExc(False)
    def __invert__(self):
        self.ops.append('invert')
        raise OpExc(14)
    def __pos__(self):
        self.ops.append('pos')
        raise OpExc(15)
    def __neg__(self):
        self.ops.append('neg')
        raise OpExc(16)
    def __repr__(self):
        self.ops.append('repr')
        raise OpExc('<OpRecorder 17>')
        
    # right-hand binary arithmetic operations
    def __radd__(self, other):
        self.ops.append('radd')
        raise OpExc(101)
    def __rsub__(self, other):
        self.ops.append('rsub')
        raise OpExc(102)
    def __rmul__(self, other):
        self.ops.append('rmul')
        raise OpExc(103)
    def __rdiv__(self, other):
        self.ops.append('rdiv')
        raise OpExc(104)
    def __rtruediv__(self, other):
        self.ops.append('rtruediv')
        raise OpExc(105)
    def __rfloordiv__(self, other):
        self.ops.append('rfloordiv')
        raise OpExc(106)
    def __rmod__(self, other):
        self.ops.append('rmod')
        raise OpExc(107)
    def __rpow__(self, other):
        self.ops.append('rpow')
        raise OpExc(108)
    def __rlshift__(self, other):
        self.ops.append('rlshift')
        raise OpExc(109)
    def __rrshift__(self, other):
        self.ops.append('rrshift')
        raise OpExc(110)
    def __rand__(self, other):
        self.ops.append('rand')
        raise OpExc(111)
    def __ror__(self, other):
        self.ops.append('ror')
        raise OpExc(112)
    def __rxor__(self, other):
        self.ops.append('rxor')
        raise OpExc(113)

    # In-place binary arithmetic operations
    def __iadd__(self, other):
        self.ops.append('iadd')
        raise OpExc(1001)
    def __isub__(self, other):
        self.ops.append('isub')
        raise OpExc(1002)
    def __imul__(self, other):
        self.ops.append('imul')
        raise OpExc(1003)
    def __idiv__(self, other):
        self.ops.append('idiv')
        raise OpExc(1004)
    def __itruediv__(self, other):
        self.ops.append('itruediv')
        raise OpExc(1005)
    def __ifloordiv__(self, other):
        self.ops.append('ifloordiv')
        raise OpExc(1006)
    def __imod__(self, other):
        self.ops.append('imod')
        raise OpExc(1007)
    def __ipow__(self, other):
        self.ops.append('ipow')
        raise OpExc(1008)
    def __ilshift__(self, other):
        self.ops.append('ilshift')
        raise OpExc(1009)
    def __irshift__(self, other):
        self.ops.append('irshift')
        raise OpExc(1010)
    def __iand__(self, other):
        self.ops.append('iand')
        raise OpExc(1011)
    def __ior__(self, other):
        self.ops.append('ior')
        raise OpExc(1012)
    def __ixor__(self, other):
        self.ops.append('ixor')
        raise OpExc(1013)

class OperatorRaisingTests(unittest.TestCase):
    def test_basic_arithmetic(self):
        operators = ('+', '-', '*', '/', '//', '%', '**',
                     '<<', '>>', '&', '|', '^')
        parts = []
        for idx, op in enumerate(operators):
            parts.extend([
                'def regular_%s(x): x %s 1' % (idx, op),
                'def reverse_%s(x): 1 %s x' % (idx, op),
                'def inplace_%s(x): x %s= 1' % (idx, op),
            ])
        testcode = '\n'.join(parts)
        co = compile(testcode, 'basic_arithmetic', 'exec',
                     flags=0, dont_inherit=True)
        namespace = {}
        exec co in namespace
        
        non_llvm_results = []
        non_llvm_raiser = OpRaiser()
        for idx, op in enumerate(operators):
            for fname in ('regular', 'reverse', 'inplace'):
                f = namespace['%s_%s' % (fname, idx)]
                try:
                    f(non_llvm_raiser)
                except OpExc, e:
                    non_llvm_results.append(e)
        self.assertEquals(len(non_llvm_raiser.ops), len(operators) * 3)
        self.assertEquals(len(non_llvm_results), len(operators) * 3)
        self.assertEquals(len(set(non_llvm_results)),
                          len(non_llvm_results))

        llvm_results = []
        llvm_raiser = OpRaiser()
        for idx, op in enumerate(operators):
            for fname in ('regular', 'reverse', 'inplace'):
                f = namespace['%s_%s' % (fname, idx)]
                f.__code__.__use_llvm__ = True
                try:
                    f(llvm_raiser)
                except OpExc, e:
                    llvm_results.append(e)

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_raiser.ops, llvm_raiser.ops)

    def test_truediv(self):
        truedivcode = '\n'.join(['def regular(x): x / 1',
                                 'def reverse(x): 1 / x',
                                 'def inplace(x): x /= 1',
        ])
        co = compile(truedivcode, 'truediv_arithmetic', 'exec',
                     flags=__future__.division.compiler_flag,
                     dont_inherit=True)
        namespace = {}
        exec co in namespace

        non_llvm_results = []
        non_llvm_raiser = OpRaiser()
        for fname in ('regular', 'reverse', 'inplace'):
            f = namespace[fname]
            try:
                f(non_llvm_raiser)
            except OpExc, e:
                non_llvm_results.append(e)
        self.assertEquals(len(non_llvm_raiser.ops), 3)
        self.assertEquals(len(non_llvm_results), 3)
        self.assertEquals(len(set(non_llvm_results)),
                          len(non_llvm_results))

        llvm_results = []
        llvm_raiser = OpRaiser()
        for fname in ('regular', 'reverse', 'inplace'):
            f = namespace[fname]
            f.__code__.__use_llvm__ = True
            try:
                f(llvm_raiser)
            except OpExc, e:
                llvm_results.append(e)

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_raiser.ops, llvm_raiser.ops)

    def test_unary(self):
        funcs = (lambda x: not x,
                 lambda x: ~x,
                 lambda x: +x,
                 lambda x: -x,
                 lambda x: `x`)

        non_llvm_results = []
        non_llvm_raiser = OpRaiser()
        for f in funcs:
            try:
                f(non_llvm_raiser)
            except OpExc, e:
                non_llvm_results.append(e)
        self.assertEquals(len(non_llvm_raiser.ops), 5)
        self.assertEquals(len(non_llvm_results), 5)
        self.assertEquals(len(set(non_llvm_results)),
                          len(non_llvm_results))

        llvm_results = []
        llvm_raiser = OpRaiser()
        for f in funcs:
            f.__code__.__use_llvm__ = True
            try:
                f(llvm_raiser)
            except OpExc, e:
                llvm_results.append(e)

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_raiser.ops, llvm_raiser.ops)

def test_main():
    run_unittest(LlvmTests, OperatorTests, OperatorRaisingTests)


if __name__ == "__main__":
    test_main()
