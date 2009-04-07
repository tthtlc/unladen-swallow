# Tests for our minimal LLVM wrappers

from test.test_support import run_unittest, findfile
import sys
import traceback
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

    def test_return_from_loop(self):
        def loop(range):
            for i in range:
                return i
        loop.__code__.__use_llvm__ = True
        self.assertEquals(1, loop([1,2,3]))

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
        # error cases tested in RaisingOperatorTests.

    def test_opcodes(self):
        # Test some specific opcodes
        def pop_top(x):
            x
            x
            x
            
        pop_top.__code__.__use_llvm__ = True
        pop_top('pop me')

    def test_delete_fast(self):
        def delit(x):
            y = 2
            z = 3
            del y
            del x
            return z
        delit.__code__.__use_llvm__ = True
        self.assertEquals(delit(1), 3)

        def useit(x):
            del x
            return x
        useit.__code__.__use_llvm__ = True
        self.assertRaises(UnboundLocalError, useit, 1)

    def test_raise(self):
        def raisetest0(): raise
        raisetest0.__code__.__use_llvm__ = True
        class TestExc(Exception):
            pass
        exc = TestExc()
        try:
            raise exc
        except TestExc:
            orig_tb = sys.exc_info()[2]
            try:
                raisetest0()
            except TestExc, e:
                new_tb = sys.exc_info()[2]
                self.assertEquals(e, exc)
                self.assertTrue(e is exc)
                self.assertEquals(new_tb.tb_next, orig_tb)
                self.assertTrue(new_tb.tb_next is orig_tb)
            else:
                self.fail("expected exception.")

        def raisetest1(x): raise x
        raisetest1.__code__.__use_llvm__ = True
        self.assertRaises(TestExc, raisetest1, TestExc);
        self.assertRaises(TestExc, raisetest1, exc);
        try:
            raisetest1(exc)
        except Exception, e:
            self.assertEquals(e, exc)
            self.assertTrue(e is exc)
        else:
            self.fail("expected exception.")

        def raisetest2(x, y): raise x, y
        raisetest2.__code__.__use_llvm__ = True
        self.assertRaises(TestExc, raisetest2, TestExc, None);
        self.assertRaises(TestExc, raisetest2, TestExc, exc);
        try:
            raisetest2(TestExc, exc)
        except Exception, e:
            self.assertEquals(e, exc)
            self.assertTrue(e is exc)
        else:
            self.fail("expected exception.")

        def raisetest3(x, y, z): raise x, y, z
        raisetest3.__code__.__use_llvm__ = True
        self.assertRaises(TestExc, raisetest3, TestExc, None, None);
        self.assertRaises(TestExc, raisetest3, TestExc, exc, None);
        self.assertRaises(TestExc, raisetest3, TestExc, exc, orig_tb)
        try:
            raisetest3(TestExc, exc, orig_tb)
        except Exception, e:
            new_tb = sys.exc_info()[2]
            self.assertEquals(e, exc)
            self.assertTrue(e is exc)
            self.assertEquals(new_tb.tb_next, orig_tb)
            self.assertTrue(new_tb.tb_next is orig_tb)
        else:
            self.fail("expected exception.")

    def test_globals(self):
        def loadglobal():
            return sys
        loadglobal.__code__.__use_llvm__ = True
        self.assertEquals(loadglobal(), sys)
        self.assertTrue(loadglobal() is sys)

        def loadbuiltin():
            return str
        loadbuiltin.__code__.__use_llvm__ = True
        self.assertEquals(loadbuiltin(), str)
        self.assertTrue(loadbuiltin() is str)

        def nosuchglobal():
            return there_better_be_no_such_global
        self.assertRaises(NameError, nosuchglobal)

        def setglobal(x):
            global _test_global
            _test_global = x
        setglobal.__code__.__use_llvm__ = True
        testvalue = "test global value"
        setglobal(testvalue)
        self.assertTrue('_test_global' in globals())
        self.assertEquals(_test_global, testvalue)
        self.assertEquals(globals()['_test_global'], testvalue)

        def deleteglobal():
            global _test_global
            del _test_global
        deleteglobal.__code__.__use_llvm__ = True
        deleteglobal()
        self.assertTrue('_test_global' not in globals())
        self.assertRaises(NameError, deleteglobal)

    def test_slice_objects(self):
        def do_slice(x): return x[::]
        non_llvm_result = do_slice([1, 2, 3])
        do_slice.__code__.__use_llvm__ = True
        self.assertEquals(do_slice([1, 2, 3]), non_llvm_result)
        self.assertRaises(TypeError, do_slice, 1)

    def test_slicing(self):
        def get_slice(x): return (x[:], x[1:], x[:3], x[:], x[1:3])
        non_llvm_result = get_slice(range(5))
        get_slice.__code__.__use_llvm__ = True
        self.assertEquals(get_slice(range(5)), non_llvm_result)

    def test_set_slice_none(self):
        def set_slice_none(x, y): x[:] = y
        source = ['a', 'b', 'c']
        non_llvm_result = range(5)
        set_slice_none(non_llvm_result, source)
        self.assertEquals(non_llvm_result, source)
        llvm_result = range(5)
        set_slice_none.__code__.__use_llvm__ = True
        set_slice_none(llvm_result, source)
        self.assertEquals(non_llvm_result, llvm_result)

    def test_set_slice_left(self):
        def set_slice_left(x, start, y): x[start:] = y
        source = ['a', 'b', 'c']
        non_llvm_result = range(5)
        set_slice_left(non_llvm_result, 1, source)
        self.assertEquals(non_llvm_result, [0, 'a', 'b', 'c'])
        llvm_result = range(5)
        set_slice_left.__code__.__use_llvm__ = True
        set_slice_left(llvm_result, 1, source)
        self.assertEquals(non_llvm_result, llvm_result)

    def test_set_slice_right(self):
        def set_slice_right(x, stop, y): x[:stop] = y
        source = ['a', 'b', 'c']
        non_llvm_result = range(5)
        set_slice_right(non_llvm_result, 3, source)
        self.assertEquals(non_llvm_result, ['a', 'b', 'c', 3, 4])
        llvm_result = range(5)
        set_slice_right.__code__.__use_llvm__ = True
        set_slice_right(llvm_result, 3, source)
        self.assertEquals(non_llvm_result, llvm_result)

    def test_set_slice_both(self):
        def set_slice_both(x, start, stop, y): x[start:stop] = y
        source = ['a', 'b', 'c']
        non_llvm_result = range(5)
        set_slice_both(non_llvm_result, 1, 3, source)
        self.assertEquals(non_llvm_result, [0, 'a', 'b', 'c', 3, 4])
        llvm_result = range(5)
        set_slice_both.__code__.__use_llvm__ = True
        set_slice_both(llvm_result, 1, 3, source)
        self.assertEquals(non_llvm_result, llvm_result)

    def test_load_deref(self):
        def f(): return self
        f.__code__.__use_llvm__ = True
        self.assertEquals(f(), self)
        self.assertTrue(f() is self)

    def test_unpacking(self):
        def f1(x):
            a, b, (c, d, e) = x
            return (a, b, c, d, e)
        f1.__code__.__use_llvm__ = True
        self.assertEquals(f1((1, 2, (3, 4, 5))), (1, 2, 3, 4, 5))

    def test_call_function(self):
        def f1(x):
            return x()
        f1.__code__.__use_llvm__ = True
        self.assertEquals(f1(lambda: 5), 5)

        def f2(x, y, z):
            return x(1, 2, y, 4, z)
        f2.__code__.__use_llvm__ = True
        self.assertEquals(f2(lambda *args: args, 3, 5),
                          (1, 2, 3, 4, 5))

        def f3():
            raise_exc()
        f3.__code__.__use_llvm__ = True
        def raise_exc():
            raise ValueError
        self.assertRaises(ValueError, f3)

    def test_call_varargs(self):
        def f(x, args):
            return x(1, 2, *args)
        f.__code__.__use_llvm__ = True
        def receiver(a, *args):
            return a, args
        self.assertEquals(f(receiver, (3, 4, 5)), (1, (2, 3, 4, 5)))

    def test_call_kwargs(self):
        def f(x, kwargs):
            return x(a=1, **kwargs)
        f.__code__.__use_llvm__ = True
        def receiver(**kwargs):
            return kwargs
        self.assertEquals(f(receiver, {'b': 2, 'c': 3}),
                          {'a': 1, 'b': 2, 'c': 3})

    def test_call_args_kwargs(self):
        def f(x, args, kwargs):
            return x(1, d=4, *args, **kwargs)
        f.__code__.__use_llvm__ = True
        def receiver(*args, **kwargs):
            return args, kwargs
        self.assertEquals(f(receiver, (2, 3), {'e': 5, 'f': 6}),
                          ((1, 2, 3), {'d': 4, 'e': 5, 'f': 6}))

class LiteralsTests(unittest.TestCase):
    def run_check_return(self, func):
        non_llvm = func(2)
        func.__code__.__use_llvm__ = True
        self.assertEquals(func(2), non_llvm)

    def run_check_exc(self, func):
        try:
            func(2)
        except TypeError, non_llvm_exc:
            pass
        else:
            self.fail("expected exception")
        func.__code__.__use_llvm__ = True
        try:
            func(2)
        except TypeError, llvm_exc:
            pass
        else:
            self.fail("expected exception")
        self.assertEquals(llvm_exc.__class__, non_llvm_exc.__class__)
        self.assertEquals(llvm_exc.args, non_llvm_exc.args)

    def test_build_tuple(self):
        self.run_check_return(lambda x: (1, x, 3))
        self.run_check_return(lambda x: (1, x, (3, 4, x), 1))
        self.run_check_exc(lambda x: (1, x, x + ""))
        self.run_check_exc(lambda x: (1, x, (3, 4, x + ""), 1))
    
    def test_build_list(self):
        self.run_check_return(lambda x: [1, x, 3])
        self.run_check_return(lambda x: [1, x, [3, 4, x], 1])
        self.run_check_exc(lambda x: [1, x, x + ""])
        self.run_check_exc(lambda x: [1, x, [3, 4, x + ""], 1])

    def test_build_map(self):
        self.run_check_return(lambda x: {1: x, 3: "4"})
        self.run_check_return(lambda x: {1: "1", x: {3: 4} })
        self.run_check_exc(lambda x: {1: x, x + "": 4})
        self.run_check_exc(lambda x: {1: x, {3: 4, x + "": 3}: 1})


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
    def run_and_compare(self, testfunc, expected_num_ops,
                        expected_num_results):
        non_llvm_results = {}
        non_llvm_recorder = OpRecorder()
        testfunc(non_llvm_recorder, non_llvm_results)
        self.assertEquals(len(non_llvm_recorder.ops), expected_num_ops)
        self.assertEquals(len(non_llvm_results), expected_num_results)
        self.assertEquals(len(set(non_llvm_results.values())),
                          len(non_llvm_results))
        
        testfunc.__code__.__use_llvm__ = True
        llvm_results = {}
        llvm_recorder = OpRecorder()
        testfunc(llvm_recorder, llvm_results)

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_recorder.ops, llvm_recorder.ops)

    def test_basic_arithmetic(self):
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
                             expected_num_ops=num_ops,
                             expected_num_results=num_ops)

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
        del namespace['__builtins__']
        self.run_and_compare(namespace['test'], expected_num_ops=3,
                             expected_num_results=3)

    def test_subscr(self):
        def testfunc(x, results):
            results['idx'] = x['item']
            x['item'] = 1
            del x['item']

        self.run_and_compare(testfunc, expected_num_ops=3,
                             expected_num_results=1)

    def test_subscr_augassign(self):
        def testfunc(x, results):
            results['item'] = x
            results['item'] += 1
            x['item'] += 1
        # expect __iadd__, __getitem__ and __setitem__ on x.
        self.run_and_compare(testfunc, expected_num_ops=3,
                             expected_num_results=1)

    def test_unary(self):
        def testfunc(x, results):
            results['not'] = not x
            results['invert'] = ~x
            results['pos'] = +x
            results['neg'] = -x
            results['convert'] = `x`

        self.run_and_compare(testfunc, expected_num_ops=5,
                             expected_num_results=5)

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
    def run_and_compare(self, namespace, argument_factory=OpRaiser):
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
            func.__code__.__use_llvm__ = True
            try:
                func(llvm_raiser)
            except OpExc, e:
                llvm_results.append(e)
        llvm_raiser.recording = False

        self.assertEquals(non_llvm_results, llvm_results)
        self.assertEquals(non_llvm_raiser.ops, llvm_raiser.ops)

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
        # Compile in a single codeblock to avoid (current) LLVM
        # exec overhead.
        testcode = '\n'.join(parts)
        co = compile(testcode, 'basic_arithmetic', 'exec',
                     flags=0, dont_inherit=True)
        namespace = {}
        exec co in namespace
        del namespace['__builtins__']
        self.run_and_compare(namespace)
        
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
        del namespace['__builtins__']
        self.run_and_compare(namespace)

    def test_unary(self):
        funcs = {'not': lambda x: not x,
                 'invert': lambda x: ~x,
                 'pos': lambda x: +x,
                 'neg': lambda x: -x,
                 'convert': lambda x: `x`}

        self.run_and_compare(funcs)

    def test_subscr(self):
        def getitem(x): x['item']
        def setitem(x): x['item'] = 1
        def delitem(x): del x['item']

        self.run_and_compare({'getitem': getitem, 'setitem': setitem,
                              'delitem': delitem})

    def test_subscr_augassign(self):
        def setitem(x): x['item'] += 1
        # Test x.__getitem__ raising an exception
        self.run_and_compare({'setitem': setitem})
        # Test x.__setitem__ raising an exception
        class HalfOpRaiser(OpRaiser):
            def __getitem__(self, item):
                # Not recording this operation, we care about __setitem__.
                return 1
        self.run_and_compare({'setitem': setitem},
                             argument_factory=HalfOpRaiser)
        # Test <item> += 1 raising an exception
        class OpRaiserProvider(OpRaiser):
            def __init__(self):
                OpRaiser.__init__(self)
                self.opraiser = None
            def __cmp__(self, other):
                return cmp((self.ops, self.opraiser), other)
            def __getitem__(self, item):
                self.ops.append('getitem')
                self.opraiser = OpRaiser()
                return self.opraiser
        self.run_and_compare({'setitem': setitem},
                             argument_factory=OpRaiserProvider)

    def test_listcomp(self):
        def listcomp(x): [ item + 5 for item in x ]
        non_llvm_recorders = [OpRecorder(), OpRecorder(), OpRaiser(),
                              OpRecorder()]
        try:
            listcomp(non_llvm_recorders)
        except OpExc, non_llvm_exc:
            pass
        else:
            self.fail('expected exception')
        self.assertEquals([o.ops for o in non_llvm_recorders],
                          [['add'], ['add'], ['add'], []])

        listcomp.__code__.__use_llvm__ = True
        llvm_recorders = [OpRecorder(), OpRecorder(), OpRaiser(),
                          OpRecorder()]
        try:
            listcomp(llvm_recorders)
        except OpExc, llvm_exc:
            pass
        else:
            self.fail('expected exception')

        for o in non_llvm_recorders + llvm_recorders:
            o.recording = False
        self.assertEquals(non_llvm_recorders, llvm_recorders)
        self.assertEquals(non_llvm_exc, llvm_exc)

class ComparisonReporter(object):
    def __cmp__(self, other):
        return 'cmp'
    def __eq__(self, other):
        return 'eq'
    def __ne__(self, other):
        return 'ne'
    def __lt__(self, other):
        return 'lt'
    def __le__(self, other):
        return 'le'
    def __gt__(self, other):
        return 'gt'
    def __ge__(self, other):
        return 'ge'

class ComparisonRaiser(object):
    def __cmp__(self, other):
        raise RuntimeError, 'cmp should not be called'
    def __eq__(self, other):
        raise OpExc('eq')
    def __ne__(self, other):
        raise OpExc('ne')
    def __lt__(self, other):
        raise OpExc('lt')
    def __le__(self, other):
        raise OpExc('le')
    def __gt__(self, other):
        raise OpExc('gt')
    def __ge__(self, other):
        raise OpExc('ge')
    def __contains__(self, other):
        raise OpExc('contains')

class ComparesToTypeError(TypeError):
    def __eq__(self, other):
        return isinstance(other, TypeError) and self.args == other.args

class ComparisonTests(unittest.TestCase):
    def compare_results(self, f, test_data):
        for use_llvm in (False, True):
            f.__code__.__use_llvm__ = use_llvm
            for x, y, expected_result in test_data:
                real_result = f(x, y)
                msg = "%s(%r, %r) expecting %r, got %r" % (
                    f.__name__, x, y, expected_result, real_result)
                self.assertEquals(expected_result, real_result, msg)

    def compare_exceptions(self, f, exc_data):
        for use_llvm in (False, True):
            f.__code__.__use_llvm__ = use_llvm
            for x, y, expected_exception in exc_data:
                try:
                    f(x, y)
                except Exception, real_exception:
                    pass
                else:
                    self.fail("%s(%r, %r) expecting %r, got nothing" % (
                        f.__name__, x, y, expected_exception))
                msg = "%s(%r, %r) expecting %r, got %r" % (
                    f.__name__, x, y, expected_exception, real_exception)
                self.assertEquals(expected_exception, real_exception, msg)

    def test_is(self):
        def is_(x, y): return x is y
        one = 1
        reporter = ComparisonReporter()
        test_data = [
            (one, one, True),
            (2, 3, False),
            ([], [], False),
            (reporter, reporter, True),
            (7, reporter, False),
        ]
        self.compare_results(is_, test_data)

    def test_is_not(self):
        def is_not(x, y): return x is not y
        one = 1
        reporter = ComparisonReporter()
        test_data = [
            (one, one, False),
            (2, 3, True),
            ([], [], True),
            (reporter, reporter, False),
            (7, reporter, True),
        ]
        self.compare_results(is_not, test_data)

    def test_eq(self):
        def eq(x, y): return x == y
        test_data = [
            (1, 1, True),
            (2, 3, False),
            ([], [], True),
            (ComparisonReporter(), 6, 'eq'),
            (7, ComparisonReporter(), 'eq'),
        ]
        self.compare_results(eq, test_data)
        exc_data = [
            (ComparisonRaiser(), 1, OpExc('eq')),
            (1, ComparisonRaiser(), OpExc('eq')),
        ]
        self.compare_exceptions(eq, exc_data)

    def test_ne(self):
        def ne(x, y): return x != y
        test_data = [
            (1, 1, False),
            (2, 3, True),
            ([], [], False),
            (ComparisonReporter(), 6, 'ne'),
            (7, ComparisonReporter(), 'ne'),
        ]
        self.compare_results(ne, test_data)
        exc_data = [
            (ComparisonRaiser(), 1, OpExc('ne')),
            (1, ComparisonRaiser(), OpExc('ne')),
        ]
        self.compare_exceptions(ne, exc_data)

    def test_lt(self):
        def lt(x, y): return x < y
        test_data = [
            (1, 1, False),
            (2, 3, True),
            (5, 4, False),
            ([], [], False),
            (ComparisonReporter(), 6, 'lt'),
            (7, ComparisonReporter(), 'gt'),
        ]
        self.compare_results(lt, test_data)
        exc_data = [
            (1, 1j, ComparesToTypeError(
                'no ordering relation is defined for complex numbers')),
            (ComparisonRaiser(), 1, OpExc('lt')),
            (1, ComparisonRaiser(), OpExc('gt')),
        ]
        self.compare_exceptions(lt, exc_data)

    def test_le(self):
        def le(x, y): return x <= y
        test_data = [
            (1, 1, True),
            (2, 3, True),
            (5, 4, False),
            ([], [], True),
            (ComparisonReporter(), 6, 'le'),
            (7, ComparisonReporter(), 'ge'),
        ]
        self.compare_results(le, test_data)
        exc_data = [
            (1, 1j, ComparesToTypeError(
                'no ordering relation is defined for complex numbers')),
            (ComparisonRaiser(), 1, OpExc('le')),
            (1, ComparisonRaiser(), OpExc('ge')),
        ]
        self.compare_exceptions(le, exc_data)

    def test_gt(self):
        def gt(x, y): return x > y
        test_data = [
            (1, 1, False),
            (2, 3, False),
            (5, 4, True),
            ([], [], False),
            (ComparisonReporter(), 6, 'gt'),
            (7, ComparisonReporter(), 'lt'),
        ]
        self.compare_results(gt, test_data)
        exc_data = [
            (1, 1j, ComparesToTypeError(
                'no ordering relation is defined for complex numbers')),
            (ComparisonRaiser(), 1, OpExc('gt')),
            (1, ComparisonRaiser(), OpExc('lt')),
        ]
        self.compare_exceptions(gt, exc_data)

    def test_ge(self):
        def ge(x, y): return x >= y
        test_data = [
            (1, 1, True),
            (2, 3, False),
            (5, 4, True),
            ([], [], True),
            (ComparisonReporter(), 6, 'ge'),
            (7, ComparisonReporter(), 'le'),
        ]
        self.compare_results(ge, test_data)
        exc_data = [
            (1, 1j, ComparesToTypeError(
                'no ordering relation is defined for complex numbers')),
            (ComparisonRaiser(), 1, OpExc('ge')),
            (1, ComparisonRaiser(), OpExc('le')),
        ]
        self.compare_exceptions(ge, exc_data)

    def test_in(self):
        def in_(x, y): return x in y
        test_data = [
            (1, [1, 2], True),
            (1, [0, 2], False),
        ]
        self.compare_results(in_, test_data)
        exc_data = [
            ([1, 2], 1, ComparesToTypeError(
                "argument of type 'int' is not iterable")),
            (1, ComparisonRaiser(), OpExc('contains')),
        ]
        self.compare_exceptions(in_, exc_data)

    def test_not_in(self):
        def not_in(x, y): return x not in y
        test_data = [
            (1, [1, 2], False),
            (1, [0, 2], True),
        ]
        self.compare_results(not_in, test_data)
        exc_data = [
            ([1, 2], 1, ComparesToTypeError(
                "argument of type 'int' is not iterable")),
            (1, ComparisonRaiser(), OpExc('contains')),
        ]
        self.compare_exceptions(not_in, exc_data)
        
def test_main():
    run_unittest(LlvmTests, LiteralsTests, OperatorTests,
                 OperatorRaisingTests, ComparisonTests)

if __name__ == "__main__":
    test_main()
