package ncsusoftware;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;

import java.util.Optional;
import java.util.Scanner;
import java.io.File;
import java.io.FileNotFoundException;

import py4j.GatewayServer;

public class Main {
    
    public static void main(String[] args) throws Exception {
        // uncomment to see an example of the this transformation (for canonicalization of assertion)
        // thisTransformationSampler();        
        // methodTransplantation();

        GatewayServer gatewayServer = new GatewayServer(new PY4JGateway());
        gatewayServer.start();
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
            ThisTransformer methodCounter = new ThisTransformer();
            methodCounter.visitStmt(stmt);

            System.out.println(stmt);
        }
    }

}