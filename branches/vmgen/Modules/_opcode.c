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

typedef struct idx_combination {
	int prefix;      /* instruction or superinstruction prefix index */
	int lastprim;    /* most recently added instruction index	*/
	int combination; /* resulting superinstruction index	     */
} IdxCombination;

static IdxCombination peephole_table[] = {
#include "ceval-peephole.i"
};

static PyObject *
init_superinstruction_table(void)
{
    Py_ssize_t i;
    PyObject *table = NULL, *key = NULL, *value = NULL;

    table = PyDict_New();
    if (table == NULL)
        goto err;

    for (i = 0; i < sizeof(peephole_table)/sizeof(peephole_table[0]); i++) {
        IdxCombination *c   = &(peephole_table[i]);

        key = Py_BuildValue("ii", c->prefix, c->lastprim);
        value = PyInt_FromLong(c->combination);
        if (key == NULL || value == NULL)
            goto err;
        if (PyDict_SetItem(table, key, value) != 0)
            goto err;
        Py_CLEAR(key);
        Py_CLEAR(value);
    }
    return table;

err:
    Py_XDECREF(table);
    Py_XDECREF(key);
    Py_XDECREF(value);
    return NULL;
}

PyMODINIT_FUNC
init_opcode(void)
{
    PyObject *m;

    m = Py_InitModule3("_opcode", NULL, "Opcode definition module.");
    if (m != NULL) {
        PyObject *opcode_list, *superinstruction_table;
        opcode_list = init_opcode_names();
        if (opcode_list != NULL)
            PyModule_AddObject(m, "opcodes", opcode_list);

        superinstruction_table = init_superinstruction_table();
        if (superinstruction_table != NULL)
            PyModule_AddObject(m, "superinstruction_table", superinstruction_table);
    }
}
