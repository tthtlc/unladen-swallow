#!/usr/bin/awk -f
# Mangle VMGEN output, evilly.

/\/\*  \*\// { next }
/^#line/     { next }

/^IF___none__TOS/ { next }
/^__none__/       { next }
/^incref/         { next }
/^decref/         { next }
/^next/           { next }

/[ \t]+$/ { sub(/[ \t]+$/, "") }

BEGIN               { s = 0 }
/^#ifdef VM_DEBUG$/ { s = 1 }
s == 0              { print }
s == 1              {       }
/^#endif$/          { s = 0 }

# eof
