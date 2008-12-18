#!/usr/bin/awk -f
# Generate the body of the big switch statement in translate_code().

NF == 2 && $1 ~ /[_A-Z]+/ && $2 ~ /[0-9]+/ {
        print "case " $1 ":"
        printf "        " "gen_" tolower($1) "(ctp"
        if ($2 >= 90) { # HAVE_ARGUMENT
                print ", oparg);"
                print "        " "blanks++;"
        } else {
                print ");"
        }
        print "        " "break;"
}

# eof
