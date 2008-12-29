/* Definitions for instructions */

#ifndef Py_INSTRUCTIONSOBJECT_H
#define Py_INSTRUCTIONSOBJECT_H
#ifdef __cplusplus
extern "C" {
#endif

PyAPI_DATA(PyTypeObject) PyInstructions_Type;

/* Opcode/arg list in a format that can be persisted to .pyc
   files. That is, it contains no pointers. Usually when !is_arg,
   opcode_or_arg will be a vmgen operation index, but from the start
   of compilation until most of the way through PyCode_Optimize() it's
   a value from opcode.h instead. */
typedef struct {
    unsigned int is_arg : 1;
    unsigned int opcode_or_arg : 31;
} PyPInst;

static inline int PyPInst_GET_OPCODE(PyPInst* inst) {
    assert(inst->is_arg == 0);
    return inst->opcode_or_arg;
}

static inline int PyPInst_GET_ARG(PyPInst* inst) {
    assert(inst->is_arg == 1);
    return inst->opcode_or_arg;
}

static inline void PyPInst_SET_OPCODE(PyPInst* inst, unsigned int opcode) {
    inst->is_arg = 0;
    inst->opcode_or_arg = opcode;
}

static inline void PyPInst_SET_ARG(PyPInst* inst, unsigned int arg) {
    inst->is_arg = 1;
    inst->opcode_or_arg = arg;
}

typedef struct {
    PyObject_VAR_HEAD
    PyPInst inst[0];
    /* 'inst' always contains enough space for 'ob_size'
       elements. */
} PyInstructionsObject;

#define PyInstructions_Check(op) (Py_TYPE(op) == &PyInstructions_Type)

/* This can also be used to allocate PyPInstVec instances by passing
   *vec==NULL. On error, frees *vec, sets it to NULL, and returns -1. */
PyInstructionsObject *_PyInstructions_New(Py_ssize_t size);

/* This can also be used to allocate PyPInstVec instances by passing
   *vec==NULL. On error, frees *vec, sets it to NULL, and returns -1. */
int _PyInstructions_Resize(PyInstructionsObject **vec, Py_ssize_t new_size);

/* Returns a new PyInstructions.  On error, returns NULL and sets the
   current exception.  The sequence is expected to contain integral
   elements.  Each element 'x' will be converted to a PyPInst as follows:
     pinst.is_arg = x & 1;
     pinst.opcode_or_arg = x >> 1;
   */
PyObject *PyInstructions_FromSequence(PyObject *seq);

/* See code.h for the runtime format of the threaded interpreter. */

#ifdef __cplusplus
}
#endif
#endif /* !Py_INSTRUCTIONSOBJECT_H */
