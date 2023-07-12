package ncsusoftware;

import java.lang.String;

import java.util.Arrays;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedConstructorDeclaration;
import com.github.javaparser.resolution.types.ResolvedReferenceType;

import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.type.ClassOrInterfaceType;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.AssignExpr;
import com.github.javaparser.ast.expr.ObjectCreationExpr;

public class AbstractionVisitor extends VoidVisitorAdapter<Integer> {
    /*
        Creating a dictionary for each line of test prefix: 
        allLines:
            {
                1:
                    {
                        "methods":
                            {
                                [
                                    "method1":
                                        {
                                            "path": "<path>",
                                            "package": "<package>",
                                            "class": "<class>",
                                            "body": "<body>"
                                        },
                                    "method2":
                                        {
                                            "path": "<path>",
                                            "package": "<package>",
                                            "class": "<class>",
                                            "body": "<body>"
                                        }
                                ]
                            }
                        "classes":
                            {
                                [
                                    "class1":
                                        {
                                            "path": "<path>",
                                            "package": "<package>",
                                            "class": "<class>"
                                        },
                                    "class2":
                                        {
                                            "path": "<path>",
                                            "package": "<package>",
                                            "class": "<class>"
                                        }
                                ]
                            }
                    }
                2:
                ...
            }
    */
    Map<Integer, Map<String, Map<String, Map<String, String>>>> perLine = null;

    AbstractionVisitor() {
        perLine = new LinkedHashMap<>();
    }

    @Override
    public void visit(final MethodCallExpr n, final Integer lineCounter) {
        super.visit(n, lineCounter);

        Map<String, String> callDetailsMap = new LinkedHashMap<>();
        try{
            ResolvedMethodDeclaration reMethodDecl = n.resolve();
            String _methodName = n.getName().asString();
            String _path = reMethodDecl.getQualifiedName();
            String _package = reMethodDecl.getPackageName();
            String _class = reMethodDecl.getClassName();
            String _body = "";

            Optional<MethodDeclaration> opt = reMethodDecl.toAst(MethodDeclaration.class);
            if(opt.isPresent()){
                _body = opt.get().toString();
            }

            callDetailsMap.put("path", _path);
            callDetailsMap.put("package", _package);
            callDetailsMap.put("class", _class);
            callDetailsMap.put("name", _methodName);
            callDetailsMap.put("body", _body);

            if(!perLine.containsKey(lineCounter)){
                perLine.put(lineCounter, new LinkedHashMap<String, Map<String, Map<String, String>>>());
                perLine.get(lineCounter).put("constructors", new LinkedHashMap<String, Map<String, String>>());
                perLine.get(lineCounter).put("methods", new LinkedHashMap<String, Map<String, String>>());
                perLine.get(lineCounter).put("classes", new LinkedHashMap<String, Map<String, String>>());
                perLine.get(lineCounter).put("vars", new LinkedHashMap<String, Map<String, String>>());
            }
            
            String key = _class + "." + _methodName;
            perLine.get(lineCounter).get("methods").put(key, callDetailsMap);
        }catch(Exception e){
            System.out.println("\nException when resolving type of " + n.getName().asString() + "\n");
            // e.printStackTrace();
        }
    }

    @Override
    public void visit(final ObjectCreationExpr n, final Integer lineCounter) {
        super.visit(n, lineCounter);

        Map<String, String> callDetailsMap = new LinkedHashMap<>();
        try{
            ResolvedConstructorDeclaration reConstructorDecl = n.resolve();
            String _constructorName = reConstructorDecl.getName();
            String _path = reConstructorDecl.getQualifiedName();
            String _package = reConstructorDecl.getPackageName();
            String _class = reConstructorDecl.getClassName();
            String _body = "";

            Optional<ConstructorDeclaration> opt = reConstructorDecl.toAst(ConstructorDeclaration.class);
            if(opt.isPresent()){
                _body = opt.get().toString();
            }

            callDetailsMap.put("path", _path);
            callDetailsMap.put("package", _package);
            callDetailsMap.put("class", _class);
            callDetailsMap.put("name", _constructorName);
            callDetailsMap.put("body", _body);

            if(!perLine.containsKey(lineCounter)){
                perLine.put(lineCounter, new LinkedHashMap<String, Map<String, Map<String, String>>>());
                perLine.get(lineCounter).put("constructors", new LinkedHashMap<String, Map<String, String>>());
                perLine.get(lineCounter).put("methods", new LinkedHashMap<String, Map<String, String>>());
                perLine.get(lineCounter).put("classes", new LinkedHashMap<String, Map<String, String>>());
                perLine.get(lineCounter).put("vars", new LinkedHashMap<String, Map<String, String>>());
            }
            
            String key = _class + "." + _constructorName;
            perLine.get(lineCounter).get("constructors").put(key, callDetailsMap);
        }catch(Exception e){
            System.out.println("\nException when resolving type of " + "constructor" + "\n");
            // e.printStackTrace();
        }
    }

    @Override
    public void visit(final ClassOrInterfaceType n, final Integer lineCounter) {
        super.visit(n, lineCounter);

        if(!n.getName().toString().contains("Exception")){
            try{
                Map<String, String> classDetailsMap = new LinkedHashMap<>();

                ResolvedReferenceType refType = n.resolve().asReferenceType();
                
                String _class = n.getName().toString();
                String _path = refType.getQualifiedName();
                String _package = _path.replace("."+_class, "");
                String _body = "";

                classDetailsMap.put("path", _path);
                classDetailsMap.put("package", _package);
                classDetailsMap.put("class", _class);
                classDetailsMap.put("body", _body);

                if(!perLine.containsKey(lineCounter)){
                    perLine.put(lineCounter, new LinkedHashMap<String, Map<String, Map<String, String>>>());
                    perLine.get(lineCounter).put("constructors", new LinkedHashMap<String, Map<String, String>>());
                    perLine.get(lineCounter).put("methods", new LinkedHashMap<String, Map<String, String>>());
                    perLine.get(lineCounter).put("classes", new LinkedHashMap<String, Map<String, String>>());
                    perLine.get(lineCounter).put("vars", new LinkedHashMap<String, Map<String, String>>());
                }
                
                String key = _class;
                perLine.get(lineCounter).get("classes").put(key, classDetailsMap);
            }catch(Exception e){
                System.out.println("\nException when resolving type of " + n.getName().toString() + "\n");
            }
        }
    }

    @Override
    public void visit(final AssignExpr n, final Integer lineCounter) {
        super.visit(n, lineCounter);
        
        if(!perLine.containsKey(lineCounter)){
            perLine.put(lineCounter, new LinkedHashMap<String, Map<String, Map<String, String>>>());
            perLine.get(lineCounter).put("constructors", new LinkedHashMap<String, Map<String, String>>());
            perLine.get(lineCounter).put("methods", new LinkedHashMap<String, Map<String, String>>());
            perLine.get(lineCounter).put("classes", new LinkedHashMap<String, Map<String, String>>());
            perLine.get(lineCounter).put("vars", new LinkedHashMap<String, Map<String, String>>());
        }
        
        String key = n.getTarget().toString();
        perLine.get(lineCounter).get("vars").put(key, new LinkedHashMap<String, String>());
    }
}