#include "Python.h"

#define INST_ADDR(CODE) #CODE
static const char *const opcode_names[] = {
#include "ceval-labels.i"
NULL
};
#undef INST_ADDR

static PyObject *
init_opcode_names(void)
{
    const char *const*opcode_name;
    PyObject *opcode_list = PyList_New(0);
    if (opcode_list == NULL)
        return NULL;
    for (opcode_name = opcode_names; *opcode_name != NULL; opcode_name++) {
        PyObject *pyname = PyString_FromString(*opcode_name);
        if (pyname == NULL)
            goto err;
        if (PyList_Append(opcode_list, pyname) == -1)
            goto err;
    }
    return opcode_list;

err:
    Py_DECREF(opcode_list);
    return NULL;
}

PyMODINIT_FUNC
init_opcode(void)
{
    PyObject *m;

    m = Py_InitModule3("_opcode", NULL, "Opcode definition module.");
    if (m != NULL) {
        PyObject *opcode_list = init_opcode_names();
        if (opcode_list != NULL)
            PyModule_AddObject(m, "opcodes", opcode_list);
    }
}
