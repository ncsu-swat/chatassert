package ncsusoftware;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.StringLiteralExpr;

import java.util.Optional;
import java.util.Scanner;
import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;
import java.util.Arrays;

import java.io.File;
import java.io.FileWriter;
import java.io.FileNotFoundException;
import java.io.IOException;

public class PY4JGateway{
    String filePath;
    private JavaParser jParser;
    private CompilationUnit cu;

    PY4JGateway(){

    }

    PY4JGateway(String filePath) throws FileNotFoundException{
        setFile(filePath);
    }

    public int setFile(String filePath) throws FileNotFoundException{
        this.filePath = filePath;
        String content = new Scanner(new File(this.filePath)).useDelimiter("\\Z").next();

        this.jParser = new JavaParser();
        this.cu = ParseUtil.parseCompilationUnit(jParser, content);

        return 0;
    }

    public int inject(String methodName, String newMethod){
        MethodDeclaration newMD = null;
        try{
            System.out.println("\n\nInjecting: " + methodName);

            newMD = ParseUtil.parseMethodDeclaration(this.jParser, newMethod);
            MethodInjectorTransformer mi = new MethodInjectorTransformer(methodName, newMD);

            mi.visit(this.cu, null);
            rewriteFile(this.cu);
        }catch(RuntimeException e){
            System.out.println("Exception has occurred - {}".format(e.toString()));
            return -1;
        }

        return 0;
    }

    public int rewriteFile(CompilationUnit cu){
        FileWriter writer = null;
        try{
            writer = new FileWriter(this.filePath);
            writer.write(cu.toString());
            writer.close();
        }catch(IOException e){
            System.out.println("Exception occurred - " + e.toString());
        }

        return 0;
    }

    public String prefixHoleForMethodNotFound(String assertion, String methodNotFound){
        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(assertion).getResult();
        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
            // ParseUtil.printTypesContentsRecursively(stmt);

            PrefixInjectionTransformer holeInjector = new PrefixInjectionTransformer(stmt.toString(), methodNotFound);
            stmt.accept(holeInjector, null);

            if(holeInjector.replacements.size() > 0){
                return holeInjector.replacements.get(0);
            }else{
                return assertion;
            }
        } else {
            return assertion;
        }
    }

    public List<String> findHoleFillers(String testMethodName){
        IdFinderVisitor visitor = new IdFinderVisitor(testMethodName);
        this.cu.accept(visitor, null);

        return visitor.allFillers;
    }

    public Map<String, List<String[]>> indexMethods(String source){
        Map<String, List<String[]>> methodsToClasses = new HashMap<String, List<String[]>>();
        List<String> allJavaFiles = MethodDeclarationVisitor.listFiles(source);

        for (String javaFile: allJavaFiles){
            try{
                String content = new Scanner(new File(javaFile)).useDelimiter("\\Z").next();
                JavaParser jparser = new JavaParser();
                // compilation unit of the original file
                CompilationUnit cu = ParseUtil.parseCompilationUnit(jparser, content);

                MethodDeclarationVisitor visitor = new MethodDeclarationVisitor();
                visitor.visit(cu, null);

                String className = javaFile.substring(javaFile.lastIndexOf("/")+1, javaFile.lastIndexOf(".")).trim();
                for(int i=0; i<visitor.methods.size(); i++){
                    String methodName = (visitor.methods.get(i))[0];
                    String startLn = (visitor.methods.get(i))[1];
                    String endLn = (visitor.methods.get(i))[2];

                    if (methodsToClasses.containsKey(methodName)){
                        methodsToClasses.get(methodName).add(new String[]{ className, javaFile, startLn, endLn });
                    }else{
                        List<String[]> listToAdd = new ArrayList<String[]>();
                        listToAdd.add(new String[]{ className, javaFile, startLn, endLn });
                        
                        methodsToClasses.put(methodName, listToAdd);
                    }
                }
            }catch(Exception e){
                System.out.println("Indexing exception: " + e.toString());
            }   
        }

        // Debugging
        // for(String methodName: methodsToClasses.keySet()){
        //     System.out.println("Method: " + methodName);
            
        //     for(int i=0; i<methodsToClasses.get(methodName).size(); i++){
        //         System.out.println("Class: " + methodsToClasses.get(methodName).get(i)[0]);
        //         System.out.println("Path: " + methodsToClasses.get(methodName).get(i)[1]);
        //         System.out.println("Start: " + methodsToClasses.get(methodName).get(i)[2]);
        //         System.out.println("End: " + methodsToClasses.get(methodName).get(i)[3]);
        //         System.out.println("");
        //     }
        // }

        return methodsToClasses;
    }

    public Map<String, String> lhs2rhs(String source){
        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(source).getResult();

        AssignExprVisitor visitor = new AssignExprVisitor();

        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();

            // for debugging:
            // ParseUtil.printTypesContentsRecursively(stmt);

            stmt.accept(visitor, null);
        }

        return visitor.lhs2rhs;
    }

    public String abstractStringLiterals(String assertion){
        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(assertion).getResult();

        String abstractString = assertion;

        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();

            // for debugging:
            // ParseUtil.printTypesContentsRecursively(stmt);

            stmt.walk(StringLiteralExpr.class, e -> e.setString("STR"));
            abstractString = stmt.toString();
        }

        return abstractString;
    }
}

