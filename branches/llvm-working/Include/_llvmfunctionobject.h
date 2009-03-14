/* _llvmfunction (llvm::Function wrapper) object interface */

#ifndef Py_LLVMFUNCTIONOBJECT_H
#define Py_LLVMFUNCTIONOBJECT_H
#ifdef __cplusplus
extern "C" {
#endif

/*
_llvmfunction represents an llvm::Function instance.  Only _llvmmodule
can create these, but they also know how to prettyprint themselves to
LLVM assembly.
*/

typedef struct {
    PyObject_HEAD
    /* Keep the module alive. It owns the Function. */
    PyObject *module;
    /* This has type llvm::Function*, but we can't say that in a C header. */
    void *the_function;
} PyLlvmFunctionObject;

PyAPI_DATA(PyTypeObject) PyLlvmFunction_Type;

#define PyLlvmFunction_Check(op) (Py_TYPE(op) == &PyLlvmFunction_Type)

/* Expects a string object full of LLVM bitcode. */
PyAPI_FUNC(PyObject *) _PyLlvmFunction_FromModuleAndPtr(PyObject *module,
                                                        void *llvm_function);

#ifdef __cplusplus
}
#endif
#endif /* !Py_LLVMFUNCTIONOBJECT_H */
