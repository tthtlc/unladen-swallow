#!/usr/bin/awk -f
# Generate the body of the big switch statement in translate_code().

NF == 2 && $1 ~ /[_A-Z]+/ && $2 ~ /[0-9]+/ {
        print "translatetable[" $1 "] = VMG_" $1 ";"
}

# eof
