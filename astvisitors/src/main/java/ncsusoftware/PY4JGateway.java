package ncsusoftware;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.stmt.Statement;
import com.github.javaparser.ast.stmt.BlockStmt;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.StringLiteralExpr;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.StaticJavaParser;

import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JarTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
// import com.github.javaparser.symbolsolver.javaparser.Navigator;

import java.lang.Exception;

import java.util.Optional;
import java.util.Scanner;
import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

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
        try {
          this.filePath = filePath;
          String content = new Scanner(new File(this.filePath)).useDelimiter("\\Z").next();

          this.jParser = new JavaParser();
          this.cu = ParseUtil.parseCompilationUnit(jParser, content);
        } catch(Exception e) {
          e.printStackTrace();
        }
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
        }catch(Exception e){
            e.printStackTrace();
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
        try{
            JavaParser jparser = new JavaParser();
            Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(assertion).getResult();
            if (optStmt.isPresent()) {
                com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
                // ParseUtil.printTypesContentsRecursively(stmt);

                PrefixHoleInjectionTransformer holeInjector = new PrefixHoleInjectionTransformer(stmt.toString(), methodNotFound);
                stmt.accept(holeInjector, null);

                if(holeInjector.replacements.size() > 0){
                    return holeInjector.replacements.get(0);
                }else{
                    return assertion;
                }
            } else {
                return assertion;
            }
        }catch(Exception e){
            e.printStackTrace();
        }
        return "";
    }

    public String variableHoleForVariableNotFound(String assertion, String variableNotFound){
        try{
            JavaParser jparser = new JavaParser();
            Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(assertion).getResult();
            if (optStmt.isPresent()) {
                com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
                // ParseUtil.printTypesContentsRecursively(stmt);

                VariableHoleInjectionTransformer holeInjector = new VariableHoleInjectionTransformer(stmt.toString(), variableNotFound);
                stmt.accept(holeInjector, null);

                if(holeInjector.replacements.size() > 0){
                    return holeInjector.replacements.get(0);
                }else{
                    return assertion;
                }
            } else {
                return assertion;
            }
        }catch(Exception e){
            e.printStackTrace();
        }
        return "";
    }

    public String prefixHoleForFocalKeyword(String assertion){
        try{
            JavaParser jparser = new JavaParser();
            Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(assertion).getResult();
            if (optStmt.isPresent()) {
                com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
                // ParseUtil.printTypesContentsRecursively(stmt);

                FocalHoleInjectionTransformer holeInjector = new FocalHoleInjectionTransformer(stmt.toString());
                stmt.accept(holeInjector, null);

                if(holeInjector.replacements.size() > 0){
                    return holeInjector.replacements.get(0);
                }else{
                    return assertion;
                }
            } else {
                return assertion;
            }
        }catch(Exception e){
            e.printStackTrace();
        }
        return "";
    }

    public List<String> findHoleFillers(String testMethodName, String focalMethod){
        try{
            IdFinderVisitor visitor = new IdFinderVisitor(testMethodName);
            this.cu.accept(visitor, null);

            // Adding name of the focal method as one of the hole fillers
            JavaParser jparser = new JavaParser();
            Optional<MethodDeclaration> optMd = jparser.parseMethodDeclaration(focalMethod).getResult();
            MethodDeclaration md = null;
            if(optMd.isPresent()){
                md = optMd.get();
                visitor.allFillers.add(md.getName().asString());
            }

            return visitor.allFillers;
        }catch(Exception e){
            e.printStackTrace();
        }
        return new ArrayList<String>();
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
        try{
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
        }catch(Exception e){
            e.printStackTrace();
        }
        return "";
    }

    public String removeAssertionMessage(String assertion){
        try{
            ArrayList<String> categoryOne = new ArrayList<>(Arrays.asList("assertArrayEquals", "assertEquals", "assertNotEquals", "assertSame", "assertNotSame"));
            ArrayList<String> categoryTwo = new ArrayList<>(Arrays.asList("assertTrue", "assertFalse", "assertNull", "assertNotNull"));

            JavaParser jparser = new JavaParser();
            Optional<com.github.javaparser.ast.stmt.Statement> assertionOpt = jparser.parseStatement(assertion).getResult();

            if(assertionOpt.isPresent()){
                MethodCallExpr assertionMethodCall = assertionOpt.get().asExpressionStmt().getExpression().asMethodCallExpr();
                NodeList<Expression> oldArgs = assertionMethodCall.getArguments();

                if(categoryOne.contains(assertionMethodCall.getName().asString())){
                    if(oldArgs.size() == 3){
                        if(oldArgs.get(0).isStringLiteralExpr()){
                            // Removing assertion error message
                            NodeList<Expression> newArgs = new NodeList<>(oldArgs.get(1), oldArgs.get(2));
                            assertionMethodCall.setArguments(newArgs);
                        }else if(oldArgs.get(2).isDoubleLiteralExpr()){
                            // Removing assertion delta
                            NodeList<Expression> newArgs = new NodeList<>(oldArgs.get(0), oldArgs.get(1));
                            assertionMethodCall.setArguments(newArgs);
                        }
                    }else if(oldArgs.size() == 4){
                        // Removing assertion error message and assertion delta
                        NodeList<Expression> newArgs = new NodeList<>(oldArgs.get(1), oldArgs.get(2));
                        assertionMethodCall.setArguments(newArgs);
                    }
                }else if(categoryTwo.contains(assertionMethodCall.getName().asString())){
                    if(oldArgs.size() == 2){
                        if(oldArgs.get(0).isStringLiteralExpr()){
                            // Removing assertion error message
                            NodeList<Expression> newArgs = new NodeList<>(oldArgs.get(1));
                            assertionMethodCall.setArguments(newArgs);
                        }
                    }
                }

                return assertionMethodCall.toString() + ";"; // Converting MethodCallExpr into a statement
            }
        }catch(Exception e){
            e.printStackTrace();
        }

        return assertion;
    }

    public String commutateAssertEquals(String assertion){
        try{
            // Assuming that the input assertion will always be of type assertEquals (ensure from Python client)
            JavaParser jparser = new JavaParser();
            Optional<com.github.javaparser.ast.stmt.Statement> assertionOpt = jparser.parseStatement(assertion).getResult();

            if(assertionOpt.isPresent()){
                MethodCallExpr assertionMethodCall = assertionOpt.get().asExpressionStmt().getExpression().asMethodCallExpr();

                if(assertionMethodCall.getName().asString().equals("assertEquals")){
                    NodeList<Expression> oldArgs = assertionMethodCall.getArguments();

                    if(oldArgs.size() == 2){
                        NodeList<Expression> newArgs = new NodeList<>(oldArgs.get(1), oldArgs.get(0));
                        assertionMethodCall.setArguments(newArgs);

                        return assertionMethodCall.toString() + ";"; // Converting MethodCallExpr into a statement
                    }
                }
            }
        }catch(Exception e){
            e.printStackTrace();
        }

        return assertion;
    }

    public Map<Integer, Map<String, Map<String, Map<String, String>>>> fetchMethodsClasses(String test_code, String file_path, String dir_path, ArrayList<String> dep_path) throws FileNotFoundException {
        // dir_path should be .../src/main/java
        try{
            CombinedTypeSolver combinedTypeSolver = new CombinedTypeSolver();
        
            // ReflectionTypeSolver (for java standard library packages)
            TypeSolver reflectionTypeSolver = new ReflectionTypeSolver();
            combinedTypeSolver.add(reflectionTypeSolver);
            
            //JarTypeSolver (for dependency jars)
            for(String jarPath: dep_path){
                try{
                    combinedTypeSolver.add(JarTypeSolver.getJarTypeSolver(jarPath));
                }catch(Exception e){
                    e.printStackTrace();
                }            
            }
            
            // JavaParserTypeSolver (for application and test code)
            TypeSolver javaParserTypeSolverMain = new JavaParserTypeSolver(new File(dir_path + "/main/java"));
            TypeSolver javaParserTypeSolverTest = new JavaParserTypeSolver(new File(dir_path + "/test/java"));
            combinedTypeSolver.add(javaParserTypeSolverMain);
            combinedTypeSolver.add(javaParserTypeSolverTest);

            JavaSymbolSolver javaSymbolSolver = new JavaSymbolSolver(combinedTypeSolver);
            StaticJavaParser.getParserConfiguration().setSymbolResolver(javaSymbolSolver);

            //------------------------------------------------------------------------------

            AbstractionVisitor abstractionVisitor = new AbstractionVisitor();

            CompilationUnit cu = StaticJavaParser.parse(new File(file_path));
            MethodDeclaration md = StaticJavaParser.parseMethodDeclaration(test_code);

            cu.walk(MethodDeclaration.class, _md -> {
                if(_md.getNameAsString().equals(md.getNameAsString())){
                    _md.setBody(md.getBody().get());

                    // Using AtomicReference to pass visitor argument because local variable in a lambda expression needs to be final and we need to update the lineCounter. So, the AtomicReference can be final but the Integer it holds can be modified. It's like a wrapper to update lineCounter from within the lambda expression. AtomicReference is used as a wrapper instead of Object class so that the code is robust in parallel execution (if implemented sometime).
                    final AtomicReference<Integer> lineCounter = new AtomicReference<>(Integer.valueOf(0));
                    _md.getBody().get().walk(Statement.class, stmt-> {
                        if(lineCounter.get() > 0){
                            stmt.accept(abstractionVisitor, lineCounter.get());
                        }
                        lineCounter.set(lineCounter.get() + 1);
                    });
                }
            });

            // System.out.println(abstractionVisitor.perLine);

            return abstractionVisitor.perLine;
        }catch(Exception e){
            e.printStackTrace();
        }

        return null;
    }

    public String removeTestMethodsFromTestClass(String source, String test_code){
        try{
            JavaParser jparser = new JavaParser();
            CompilationUnit cu = ParseUtil.parseCompilationUnit(jparser, source);
            Optional<MethodDeclaration> testMethodOpt = jparser.parseMethodDeclaration(test_code).getResult();

            if(testMethodOpt.isPresent()){
                // At first, we try to remove the exact test method that we are currently generating the assertion for, from the test class (to eliminate test dataset leakage)
                MethodDeclaration testMethod = testMethodOpt.get();
                
                cu.walk(MethodDeclaration.class, md -> {
                    if(md.getName().asString().equals(testMethod.getName().asString())){
                        md.getParentNode().get().remove(md);
                    }
                });
            }else{
                // If we are unable to parse the test_code, then we try to remove all the test methods from the test class (to eliminate dataset leakage)
                cu.walk(MethodDeclaration.class, md -> {
                    for(AnnotationExpr annExpr: md.getAnnotations()){
                        if(annExpr.getName().asString().contains("Test")){
                            md.getParentNode().get().remove(md);
                        }
                    }
                });
            }
            
            return cu.toString();

        }catch(Exception e){
            e.printStackTrace();
        }

        return source;
    }
}

