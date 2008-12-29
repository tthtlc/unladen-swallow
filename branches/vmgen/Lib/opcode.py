
"""
opcode module - potentially shared between dis and other modules which
operate on bytecodes (e.g. peephole optimizers).
"""

__all__ = ["cmp_op", "hasconst", "hasname", "hasjrel", "hasjabs",
           "haslocal", "hascompare", "hasfree", "opname", "opmap", "opdesc"]

import _opcode

cmp_op = ('<', '<=', '==', '!=', '>', '>=', 'in', 'not in', 'is',
        'is not', 'exception match', 'BAD')

hasconst = []
hasname = []
hasjrel = []
hasjabs = []
haslocal = []
hascompare = []
hasfree = []

opmap = {}
opname = [''] * 256
for op in range(256): opname[op] = '<%r>' % (op,)
del op

for i, name in enumerate(_opcode.opcodes):
    opname[i] = name
    opmap[name] = i
    opmap[name.upper()] = i
del i, name

opdesc = {}

def describe(name, description):
    opdesc[opmap[name]] = description

def name_op(name, description):
    op = opmap[name]
    hasname.append(op)
    opdesc[op] = description

def jrel_op(name, description):
    op = opmap[name]
    hasjrel.append(op)
    opdesc[op] = description

def jabs_op(name, description):
    op = opmap[name]
    hasjabs.append(op)
    opdesc[op] = description

# Instruction opcodes for compiled code

name_op('STORE_NAME', 'Index in name list')
name_op('DELETE_NAME', 'Index in name list')
describe('UNPACK_SEQUENCE', 'Number of tuple items')
jrel_op('FOR_ITER', '???')

name_op('STORE_ATTR', 'Index in name list')
name_op('DELETE_ATTR', 'Index in name list')
name_op('STORE_GLOBAL', 'Index in name list')
name_op('DELETE_GLOBAL', 'Index in name list')

describe('LOAD_CONST', 'Index in const list')
hasconst.append(opmap['LOAD_CONST'])
name_op('LOAD_NAME', 'Index in name list')
describe('BUILD_TUPLE', 'Number of tuple items')
describe('BUILD_LIST', 'Number of list items')
describe('BUILD_MAP', 'Number of dict entries (upto 255)')
name_op('LOAD_ATTR', 'Index in name list')
describe('COMPARE_OP', 'Comparison operator')
hascompare.append(opmap['COMPARE_OP'])
name_op('IMPORT_NAME', 'Index in name list')
name_op('IMPORT_FROM', 'Index in name list')

jrel_op('JUMP_FORWARD', 'Number of bytes to skip')
jrel_op('JUMP_IF_FALSE', 'Number of bytes to skip')
jrel_op('JUMP_IF_TRUE', 'Number of bytes to skip')
jabs_op('JUMP_ABSOLUTE', 'Target byte offset from beginning of code')

name_op('LOAD_GLOBAL', 'Index in name list')

jabs_op('CONTINUE_LOOP', 'Target address')
jrel_op('SETUP_LOOP', 'Distance to target address')
jrel_op('SETUP_EXCEPT', 'Distance to target address')
jrel_op('SETUP_FINALLY', 'Distance to target address')

describe('LOAD_FAST', 'Local variable number')
haslocal.append(opmap['LOAD_FAST'])
describe('STORE_FAST', 'Local variable number')
haslocal.append(opmap['STORE_FAST'])
describe('DELETE_FAST', 'Local variable number')
haslocal.append(opmap['DELETE_FAST'])

describe('CALL_FUNCTION', '#args + (#kwargs << 8)')
describe('MAKE_FUNCTION', 'Number of args with default values')
describe('MAKE_CLOSURE', '???')
describe('LOAD_CLOSURE', '???')
hasfree.append(opmap['LOAD_CLOSURE'])
describe('LOAD_DEREF', '???')
hasfree.append(opmap['LOAD_DEREF'])
describe('STORE_DEREF', '???')
hasfree.append(opmap['STORE_DEREF'])

describe('CALL_FUNCTION_VAR_KW',
         '((#args + (#kwargs << 8)) << 16) + code;'
         ' where code&1 is true if there\'s a *args parameter,'
         ' and code&2 is true if there\'s a **kwargs parameter.')

del describe, name_op, jrel_op, jabs_op
