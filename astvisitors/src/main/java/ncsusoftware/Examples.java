package ncsusoftware;


import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;

import java.util.Collections;
import java.util.Comparator;
import java.util.Optional;
import java.util.Scanner;
import java.io.File;
import java.io.FileNotFoundException;

public class Examples {

    public static void main(String[] args) throws FileNotFoundException {
        // methodTransplantation();
        // thisTransformationSampler();
        holeInjection();
    }
    
    private static void methodTransplantation() throws FileNotFoundException {
        // System.out.println("Working Directory = " + System.getProperty("user.dir"));
        String fileName = "src/test/java/ncsusoftware/AppTest.java";
        String content = new Scanner(new File(fileName)).useDelimiter("\\Z").next();
        // System.out.println(content);
        JavaParser jparser = new JavaParser();
        // compilation unit of the original file
        CompilationUnit cu = ParseUtil.parseCompilationUnit(jparser, content);

        // method declaration of a modified method. note that this version of testApp does not have body
        MethodDeclaration newMD = ParseUtil.parseMethodDeclaration(jparser, "public void testApp(){}");

        // build a visitor
        MethodInjectorTransformer mi = new MethodInjectorTransformer("testApp", newMD);
        // use visitor to traverse the ast and replace node of the original function with the new node
        mi.visit(cu, null);
    
        //debugging
        System.out.println(cu);
    }


    private static void thisTransformationSampler() {
        String s = "Assert.assertEquals(y, this.y.z);";
        //TODO: it crashes on this case! try generalizing to demonstrate you understood the infrastructure. -Marcelo
        // String s = "Assert.assertEquals(this.y, this.y.z);";
        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(s).getResult();
        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
            // for debugging:
            // ParseUtil.printTypesContentsRecursively(stmt);
            ThisTransformer thisTransformer = new ThisTransformer();
            thisTransformer.visitStmt(stmt);

            System.out.println(stmt);
        }
    }

    private static void holeInjection() {

        // test cases... :-/
        // String s = "Assert.assertEquals(1, a(w,t));";        
        String s = "Assert.assertEquals(\"a\", this.y.z(w, tmp));";     
        // String s = "Assert.assertEquals(false || x(), this.y.z(w));";
        // String s = "Assert.assertEquals(1.0, this.y.z(w));";        
        // String s = "Assert.assertEquals(x+1, this.y.z(w));";
        // String s = "Assert.assertEquals(x+1, this.y.z());";
        // String s = "Assert.assertEquals(x+1, this.y.z);";
        // String s = "Assert.assertEquals(y, this.y.z);";
        // String s = "Assert.assertEquals(x+1, a.b());";
        
        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(s).getResult();
        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
            // for debugging:
            ParseUtil.printTypesContentsRecursively(stmt);

            HoleInjectionTransformer holeInjector = new HoleInjectionTransformer(stmt.toString());
            stmt.accept(holeInjector, null);
            /** sort the list of candidates */
            Comparator<String> comp = new Comparator<String>() {
                @Override
                public int compare(String o1, String o2) {
                    int x = o1.length();
                    int y = o2.length();
                    return  (x > y) ? 1: (x < y) ? -1: 0;
                }
            };
            Collections.sort(holeInjector.replacements, comp);
            /** print the list of candidates */
            for (String candidate : holeInjector.replacements) {
                if (candidate.equals("<insert>;")) continue;
                /** hack! discard <insert> followed by a dot */
                if (!candidate.contains("<insert>."))
                    System.out.println(candidate);
            }

        }
    }
}
