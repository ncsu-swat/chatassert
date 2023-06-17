package ncsusoftware;

import java.io.File;
import java.io.FileNotFoundException;
import java.util.Collections;
import java.util.Comparator;
import java.util.Optional;
import java.util.Scanner;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;

public class IdFinderMain {


    public static void main(String[] args) throws FileNotFoundException {

        String fileName = "src/test/java/ncsusoftware/AnotherTest.java";
        String content = new Scanner(new File(fileName)).useDelimiter("\\Z").next();
        // System.out.println(content);
        JavaParser jparser = new JavaParser();
        // compilation unit of the original file
        CompilationUnit cu = ParseUtil.parseCompilationUnit(jparser, content);

        IdFinderVisitor visitor = new IdFinderVisitor();

        cu.accept(visitor, null);
    }

        
    

}