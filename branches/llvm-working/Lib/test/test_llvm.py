# Tests for our minimal LLVM wrappers

from test.test_support import run_unittest, findfile
import unittest
import _llvm


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
                'define private %__pyobject* @"<module>"')]
        self.assertEquals(module_data,
                          """\
; ModuleID = '<string>'
	%__function_type = type %__pyobject* (%__pyframeobject*, %__pyobject*, %__pyobject*, %__pyobject*)
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

define private %__pyobject* @foo(%__pyframeobject*, %__pyobject*, %__pyobject*, %__pyobject*) {
entry:
	%stack_pointer_addr = alloca %__pyobject**		; <%__pyobject***> [#uses=5]
	%4 = getelementptr %__pyframeobject* %0, i32 0, i32 8		; <%__pyobject***> [#uses=1]
	%initial_stack_pointer = load %__pyobject*** %4		; <%__pyobject**> [#uses=1]
	store %__pyobject** %initial_stack_pointer, %__pyobject*** %stack_pointer_addr
	%5 = getelementptr %__pyframeobject* %0, i32 0, i32 3		; <%__pycodeobject**> [#uses=1]
	%co = load %__pycodeobject** %5		; <%__pycodeobject*> [#uses=1]
	%6 = getelementptr %__pycodeobject* %co, i32 0, i32 6		; <%__pyobject**> [#uses=1]
	%7 = load %__pyobject** %6		; <%__pyobject*> [#uses=1]
	%consts = bitcast %__pyobject* %7 to %__pytupleobject*		; <%__pytupleobject*> [#uses=1]
	br label %8

; <label>:8		; preds = %entry
	%9 = getelementptr %__pytupleobject* %consts, i32 0, i32 2, i32 0		; <%__pyobject**> [#uses=1]
	%10 = load %__pyobject** %9		; <%__pyobject*> [#uses=2]
	%11 = load i32* @_Py_RefTotal		; <i32> [#uses=1]
	%12 = add i32 %11, 1		; <i32> [#uses=1]
	store i32 %12, i32* @_Py_RefTotal
	%13 = getelementptr %__pyobject* %10, i32 0, i32 2		; <i32*> [#uses=2]
	%14 = load i32* %13		; <i32> [#uses=1]
	%15 = add i32 %14, 1		; <i32> [#uses=1]
	store i32 %15, i32* %13
	%16 = load %__pyobject*** %stack_pointer_addr		; <%__pyobject**> [#uses=2]
	store %__pyobject* %10, %__pyobject** %16
	%17 = getelementptr %__pyobject** %16, i32 1		; <%__pyobject**> [#uses=1]
	store %__pyobject** %17, %__pyobject*** %stack_pointer_addr
	%18 = load %__pyobject*** %stack_pointer_addr		; <%__pyobject**> [#uses=1]
	%19 = getelementptr %__pyobject** %18, i32 -1		; <%__pyobject**> [#uses=2]
	%20 = load %__pyobject** %19		; <%__pyobject*> [#uses=1]
	store %__pyobject** %19, %__pyobject*** %stack_pointer_addr
	ret %__pyobject* %20
}
""")


def test_main():
    run_unittest(LlvmTests)


if __name__ == "__main__":
    test_main()
