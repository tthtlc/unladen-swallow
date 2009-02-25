#ifndef Py_CPICKLE_H
#define Py_CPICKLE_H
#ifdef __cplusplus
extern "C" {
#endif

/* Header file for cPickle.c. This is here so _testcapimodule.c can test the
   MemoTable implementation. */

/* Do this dance so _testcapimodule.c will build correctly, but cPickle will
   be as fast as possible. */
#ifdef NO_STATIC_MEMOTABLE
#define STATIC_MEMOTABLE
#else
#define STATIC_MEMOTABLE static
#endif

typedef struct {
	void *mte_key;
	long mte_value;
} MemoEntry;

typedef struct {
	Py_ssize_t mt_mask;
	Py_ssize_t mt_used;
	Py_ssize_t mt_allocated;
	MemoEntry *mt_table;
} MemoTable;

STATIC_MEMOTABLE MemoTable *MemoTable_New(void);
STATIC_MEMOTABLE void MemoTable_Del(MemoTable *self);

STATIC_MEMOTABLE Py_ssize_t MemoTable_Size(MemoTable *self);
STATIC_MEMOTABLE int MemoTable_Clear(MemoTable *self);
STATIC_MEMOTABLE long *MemoTable_Get(MemoTable *self, void *key);
STATIC_MEMOTABLE int MemoTable_Set(MemoTable *self, void *key, long value);


#ifdef __cplusplus
}
#endif
#endif /* !Py_CPICKLE_H */
