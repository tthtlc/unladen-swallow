#!/usr/bin/awk -f
# Generate the body of the big switch statement in disassemble_bytecode().

NF == 2 && $1 ~ /[_A-Z]+/ && $2 ~ /[0-9]+/ {
        print "case " $1 ":"
        print "        " "printf(\"%s   \", \"" $1 "\");"
        if ($2 >= 90) # HAVE_ARGUMENT
                print "        " "printf(\"%d\", oparg);"
        print "        " "break;"
}

# eof
