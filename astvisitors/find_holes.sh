#!/bin/bash

#########
## INPUT
#########
ASSERTION_TO_GENERATE_HOLES=$1

if [ -z "${ASSERTION_TO_GENERATE_HOLES}" ]
then
    echo "no input assertion provided. please, check"
    exit -1
fi

# get classpath of dependencies and store in a variable
mvn dependency:build-classpath -Dmdep.outputFile=cp.txt
cp=$(<cp.txt)
rm cp.txt

# ## demo on how to call code for "hole injection"
java -cp $cp:target/classes ncsusoftware.HoleInjectionMain ${ASSERTION_TO_GENERATE_HOLES} > out.txt

#########
## READ out.txt and delete it!
#########
