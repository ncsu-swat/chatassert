package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;

import java.util.HashMap;
import java.util.Map;
import java.util.Arrays;
import java.util.ArrayList;
import java.util.List;

import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.nodeTypes.NodeWithName;
import com.github.javaparser.ast.stmt.LocalClassDeclarationStmt;

public class IdFinderVisitor extends VoidVisitorAdapter<Void> {

    public Map<String, String> fieldDeclarations = new HashMap<String, String>();
    public Map<String, String> helperMethodDeclarations = new HashMap<String, String>();
    public Map<String, String> localVariableDeclarations = new HashMap<String, String>();
    
    public List<String> allFillers = new ArrayList<String>();
    public List<String> primitiveTypes = Arrays.asList("byte", "short", "int", "long", "float", "double", "boolean", "char");

    String testName; 

    IdFinderVisitor(String testName) {
        this.testName = testName;
    }

    @Override
    public void visit(final FieldDeclaration n, final Void arg) {
        super.visit(n, arg);
        for (VariableDeclarator vd : n.getVariables()) {
            fieldDeclarations.put(vd.getName().toString(), n.getElementType().asString());
            
            if(!primitiveTypes.contains(n.getElementType().asString())){
                allFillers.add(vd.getName().toString());
            }
        }
    }

    boolean monitorMethodBody = false;
    @Override
    public void visit(final MethodDeclaration n, final Void arg) {
        /** monitor method body for local variables only if it is the target method */
        monitorMethodBody = n.getNameAsString().equals(testName);

        super.visit(n, arg);
        /**
         * assuming helper methods do not have annotation and all others (tests) have
         */
        if (n.getAnnotations().isEmpty()) {
            helperMethodDeclarations.put(n.getNameAsString(), n.getTypeAsString());
        } 

    }

    @Override
    public void visit(final VariableDeclarator n, final Void arg) {
        super.visit(n, arg);

        /** only print if monitoring method body */
        if (monitorMethodBody) {
            localVariableDeclarations.put(n.getNameAsString(), n.getTypeAsString());
            
            if(!primitiveTypes.contains(n.getTypeAsString())){
                allFillers.add(n.getNameAsString());
            }
        }
    }

}