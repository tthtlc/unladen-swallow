# Tests for our minimal LLVM wrappers

from test.test_support import run_unittest, findfile
import _llvm
import functools
import unittest
import __future__


def at_each_optimization_level(func):
    """Decorator for test functions, to run them at each optimization level."""
    @functools.wraps(func)
    def result(self):
        for level in (-1,0,1,2):
            func(self, level)
    return result


def compile_for_llvm(function_name, def_string, optimization_level=-1):
    """Compiles function_name, defined in def_string to be run through LLVM.

    Compiles and runs def_string in a temporary namespace, pulls the
    function named 'function_name' out of that namespace, optimizes it
    at level 'optimization_level', -1 for the default optimization,
    and marks it to be JITted and run through LLVM.

    """
    namespace = {}
    exec def_string in namespace
    func = namespace[function_name]
    func.__code__.co_optimization = optimization_level
    func.__code__.__use_llvm__ = True
    return func


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

    @at_each_optimization_level
    def test_run_simple_function(self, level):
        foo = compile_for_llvm("foo", """
def foo():
    pass
""", level)
        self.assertEquals(None, foo())

    @at_each_optimization_level
    def test_return_arg(self, level):
        foo = compile_for_llvm("foo", """
def foo(a):
    return a
""", level)
        self.assertEquals(3, foo(3))
        self.assertEquals("Hello", foo("Hello"))

    @at_each_optimization_level
    def test_unbound_local(self, level):
        foo = compile_for_llvm("foo", """
def foo():
    a = a
""", level)
        try:
            foo()
        except UnboundLocalError as e:
            self.assertEquals(
                str(e), "local variable 'a' referenced before assignment")
        else:
            self.fail("Expected UnboundLocalError")

    @at_each_optimization_level
    def test_assign(self, level):
        foo = compile_for_llvm("foo", """
def foo(a):
    b = a
    return b
""", level)
        self.assertEquals(3, foo(3))
        self.assertEquals("Hello", foo("Hello"))

    @at_each_optimization_level
    def test_raising_getiter(self, level):
        class RaisingIter(object):
            def __iter__(self):
                raise RuntimeError
        loop = compile_for_llvm("loop", """
def loop(range):
    for i in range:
        pass
""", level)
        self.assertRaises(RuntimeError, loop, RaisingIter())

    @at_each_optimization_level
    def test_raising_next(self, level):
        class RaisingNext(object):
            def __iter__(self):
                return self
            def next(self):
                raise RuntimeError
        loop = compile_for_llvm("loop", """
def loop(range):
    for i in range:
        pass
""", level)
        self.assertRaises(RuntimeError, loop, RaisingNext())

    @at_each_optimization_level
    def test_loop(self, level):
        loop = compile_for_llvm("loop", """
def loop(range):
    for i in range:
        pass
""", level)
        r = iter(range(12))
        self.assertEquals(None, loop(r))
        self.assertRaises(StopIteration, next, r)

    @at_each_optimization_level
    def test_return_from_loop(self, level):
        loop = compile_for_llvm("loop", """
def loop(range):
    for i in range:
        return i
""", level)
        self.assertEquals(1, loop([1,2,3]))

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
    def __cmp__(self, other):
        return cmp(self.ops, other)
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

    # Indexing
    def __getitem__(self, item):
        self.ops.append(('getitem', item))
        return 1014
    def __setitem__(self, item, value):
        self.ops.append(('setitem', item, value))
    def __delitem__(self, item):
        self.ops.append(('delitem', item))

class OperatorTests(unittest.TestCase):
    def run_and_compare(self, testfunc, optimization_level,
                        expected_num_ops, expected_num_results):
        non_llvm_results = {}
        non_llvm_recorder = OpRecorder()
        testfunc(non_llvm_recorder, non_llvm_results)
        self.assertEquals(len(non_llvm_recorder.ops), expected_num_ops)
        self.assertEquals(len(non_llvm_results), expected_num_results)
        self.assertEquals(len(set(non_llvm_results.values())),
                          len(non_llvm_results))

        testfunc.__code__.co_optimization = optimization_level
        testfunc.__code__.__use_llvm__ = True
        llvm_results = {}
        llvm_recorder = OpRecorder()
        testfunc(llvm_recorder, llvm_results)

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_recorder.ops, llvm_recorder.ops)

    @at_each_optimization_level
    def test_basic_arithmetic(self, level):
        operators = ('+', '-', '*', '/', '//', '%', '**',
                     '<<', '>>', '&', '|', '^')
        num_ops = len(operators) * 3
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
        del namespace['__builtins__']
        self.run_and_compare(namespace['test'],
                             level,
                             expected_num_ops=num_ops,
                             expected_num_results=num_ops)

    @at_each_optimization_level
    def test_truediv(self, level):
        truedivcode = '''def test(x, results):
                             results["regular div"] = x / 1
                             results["reverse div"] = 1 / x
                             x /= 1; results["in-place div"] = x'''
        co = compile(truedivcode, 'truediv_arithmetic', 'exec',
                     flags=__future__.division.compiler_flag,
                     dont_inherit=True)
        namespace = {}
        exec co in namespace
        del namespace['__builtins__']
        self.run_and_compare(namespace['test'], level,
                             expected_num_ops=3, expected_num_results=3)

    @at_each_optimization_level
    def test_subscr(self, level):
        namespace = {}
        exec """
def testfunc(x, results):
    results['idx'] = x['item']
    x['item'] = 1
""" in namespace
        self.run_and_compare(namespace['testfunc'], level,
                             expected_num_ops=2, expected_num_results=1)

    @at_each_optimization_level
    def test_unary(self, level):
        namespace = {}
        exec """
def testfunc(x, results):
    results['not'] = not x
    results['invert'] = ~x
    results['pos'] = +x
    results['neg'] = -x
    results['convert'] = `x`
""" in namespace
        self.run_and_compare(namespace['testfunc'], level,
                             expected_num_ops=5, expected_num_results=5)

    @at_each_optimization_level
    def test_subscr_augassign(self, level):
        namespace = {}
        exec """
def testfunc(x, results):
    results['item'] = x
    results['item'] += 1
    x['item'] += 1
""" in namespace
        # expect __iadd__, __getitem__ and __setitem__ on x,
        # and one item in results.
        self.run_and_compare(namespace['testfunc'], level,
                             expected_num_ops=3, expected_num_results=1)

class OpExc(Exception):
    def __cmp__(self, other):
        return cmp(self.args, other.args)
    def __hash__(self):
        return hash(self.args)

class OpRaiser(object):
    # regular binary arithmetic operations
    def __init__(self):
        self.ops = []
        self.recording = True
    def __cmp__(self, other):
        return cmp(self.ops, other)
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
        if not self.recording:
            return '<OpRecorder %r>' % self.ops
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

    # Indexing
    def __getitem__(self, item):
        self.ops.append(('getitem', item))
        raise OpExc(1014)
    def __setitem__(self, item, value):
        self.ops.append(('setitem', item, value))
        raise OpExc(1015)
    def __delitem__(self, item):
        self.ops.append(('delitem', item))
        raise OpExc(1016)

class OperatorRaisingTests(unittest.TestCase):
    def run_and_compare(self, namespace, optimization_level,
                        argument_factory=OpRaiser):
        non_llvm_results = []
        non_llvm_raiser = argument_factory()
        funcs = namespace.items()
        funcs.sort()
        for fname, func in funcs:
            try:
                func(non_llvm_raiser)
            except OpExc, e:
                non_llvm_results.append(e)
        non_llvm_raiser.recording = False

        self.assertEquals(len(non_llvm_raiser.ops), len(funcs))
        self.assertEquals(len(non_llvm_results), len(funcs))
        self.assertEquals(len(set(non_llvm_results)),
                          len(non_llvm_results))

        llvm_results = []
        llvm_raiser = argument_factory()
        for fname, func in funcs:
            func.__code__.co_optimization = optimization_level
            func.__code__.__use_llvm__ = True
            try:
                func(llvm_raiser)
            except OpExc, e:
                llvm_results.append(e)
        llvm_raiser.recording = False

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_raiser.ops, llvm_raiser.ops)

    @at_each_optimization_level
    def test_basic_arithmetic(self, level):
        operators = ('+', '-', '*', '/', '//', '%', '**',
                     '<<', '>>', '&', '|', '^')
        parts = []
        for idx, op in enumerate(operators):
            parts.extend([
                'def regular_%s(x): x %s 1' % (idx, op),
                'def reverse_%s(x): 1 %s x' % (idx, op),
                'def inplace_%s(x): x %s= 1' % (idx, op),
            ])
        # Compile in a single codeblock to avoid (current) LLVM
        # exec overhead.
        testcode = '\n'.join(parts)
        co = compile(testcode, 'basic_arithmetic', 'exec',
                     flags=0, dont_inherit=True)
        namespace = {}
        exec co in namespace
        del namespace['__builtins__']
        self.run_and_compare(namespace, level)

    @at_each_optimization_level
    def test_truediv(self, level):
        truedivcode = '\n'.join(['def regular(x): x / 1',
                                 'def reverse(x): 1 / x',
                                 'def inplace(x): x /= 1',
        ])
        co = compile(truedivcode, 'truediv_arithmetic', 'exec',
                     flags=__future__.division.compiler_flag,
                     dont_inherit=True)
        namespace = {}
        exec co in namespace
        del namespace['__builtins__']
        self.run_and_compare(namespace, level)

    @at_each_optimization_level
    def test_unary(self, level):
        namespace = {}
        exec """
def not_(x): return not x
def invert(x): return ~x
def pos(x): return +x
def neg(x): return -x
def convert(x): return `x`
""" in namespace
        del namespace['__builtins__']
        self.run_and_compare(namespace, level)

    @at_each_optimization_level
    def test_subscr(self, level):
        namespace = {}
        exec """
def getitem(x): x['item']
def setitem(x): x['item'] = 1
""" in namespace
        del namespace['__builtins__']
        self.run_and_compare(namespace, level)

    @at_each_optimization_level
    def test_subscr_augassign_(self, level):
        # We can't reuse setitem for the different tests because
        # running it will increase the optimization level from -1 to 0.
        def make_setitem():
            namespace = {}
            exec """
def setitem(x):
    x['item'] += 1
""" in namespace
            del namespace['__builtins__']
            return namespace
        # Test x.__getitem__ raising an exception.
        self.run_and_compare(make_setitem(), level)
        # Test x.__setitem__ raising an exception.
        class HalfOpRaiser(OpRaiser):
            def __getitem__(self, item):
                # Not recording this operation, we care about __setitem__.
                return 1
        self.run_and_compare(make_setitem(), level,
                             argument_factory=HalfOpRaiser)
        # Test item.__iadd__(1) raising an exception, between the
        # x.__getitem__ and x.__setitem__ calls.
        class OpRaiserProvider(OpRaiser):
            def __init__(self):
                OpRaiser.__init__(self)
                self.opraiser = None
            def __cmp__(self, other):
                return cmp((self.ops, self.opraiser),
                           (other.ops, other.opraiser))
            def __getitem__(self, item):
                self.ops.append('getitem')
                self.opraiser = OpRaiser()
                return self.opraiser
        self.run_and_compare(make_setitem(), level,
                             argument_factory=OpRaiserProvider)

def test_main():
    run_unittest(LlvmTests, OperatorTests, OperatorRaisingTests)


if __name__ == "__main__":
    test_main()