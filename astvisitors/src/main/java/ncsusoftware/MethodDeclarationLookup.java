package ncsusoftware;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

import java.lang.reflect.Method; // <== Using reflection to find type!

public class MethodDeclarationLookup {

    public static void main(String[] args) throws ClassNotFoundException, IOException, NoSuchFieldException, SecurityException, IllegalArgumentException, IllegalAccessException {

        /** these are example inputs */
        String source = "/Users/adminuser/Documents/Work/Experiment/ChatGPT/oragen-main/src/tmp/repos/hazelcast-simulator";
        List<String> typeNames = Arrays.asList(new String[]{"Worker", "WorkerOperationProcessor"}); // <= you should use app names extracted with idfinder        
        String methodName = "shutdown";

        List<Class<?>> appClassesOfInterest = findClassesOfInterest(source, typeNames);
        for (Class<?> c: appClassesOfInterest) {
            for (Method m : c.getMethods()) {
                if (m.getName().contains(methodName)) {
                    System.out.printf("**** class %s declares method %s\n", c.getName(), m.getName());
                }
            }
        }

    }

    public static Map<String, List<String>> indexClassesToMethods(String source){
        Map<String, List<String>> classesToMethods = new HashMap<String, List<String>>();
        List<Class<?>> appAllClasses = findClassesFromSource(source);
        
        for (Class<?> c: appAllClasses) {
            String fullName = c.getName();
            String cname = fullName.substring(fullName.lastIndexOf(".")+1);

            List<String> listOfMethodsInClass = new ArrayList<String>();
            for (Method m : c.getMethods()) {
                System.out.println(cname + ": " + m.getName());

                listOfMethodsInClass.add(m.getName());
            }
            classesToMethods.put(cname, listOfMethodsInClass);
        }

        return classesToMethods;
    }

    public static Map<String, List<String>> indexMethodsToClasses(String source){
        Map<String, List<String>> methodsToClasses = new HashMap<String, List<String>>();
        List<Class<?>> appAllClasses = findClassesFromSource(source);
        for (Class<?> c: appAllClasses) {
            String fullName = c.getName();
            String cname = fullName.substring(fullName.lastIndexOf(".")+1);

            for (Method m : c.getMethods()) {
                if(methodsToClasses.containsKey(m.getName())){
                    methodsToClasses.get(m.getName()).add(cname);
                }else{
                    methodsToClasses.put(m.getName(), new ArrayList<String>());
                }
            }
        }

        return methodsToClasses;
    }

    /******** utility functions */

    private static List<Class<?>> findClassesOfInterest(String source, List<String> typeNames)
            throws FileNotFoundException, IOException, ClassNotFoundException {
        /** find classes (reflection representation) of project */
        List<Class<?>> appClasses = findClassesFromSource(source);
        // System.out.println(appClasses);
        /** reducing the scope of the search */
        List<Class<?>> appClassesOfInterest = new ArrayList<Class<?>>();
        for (Class<?> clazz : appClasses) {
            String fullName = clazz.getName();
            String cname = fullName.substring(fullName.lastIndexOf(".")+1);
            if (typeNames.contains(cname)) appClassesOfInterest.add(clazz);
        }
        return appClassesOfInterest;
    }    

    private static List<Class<?>> findClassesFromSource(String source) {
        List<Class<?>> appClasses = new ArrayList<Class<?>>();
        try{
            for (File f : listFilesForFolder(new File(source), ".java")) {
                System.out.println(f);

                String fileName = f.getName();
                String className = fileName.substring(fileName.lastIndexOf("/")+1, fileName.lastIndexOf(".")).trim();
                String packageLine = readPackageLine(f);
                String packageName = packageLine.substring(packageLine.indexOf(" "), packageLine.indexOf(";")).trim();            
                // System.out.println(packageName+"."+className);
                /** skip test classes */
                if (className.contains("Test")) continue;
                Class<?> clazz = Class.forName(packageName+"."+className);
                appClasses.add(clazz);
            }
        }catch(FileNotFoundException e){
            System.out.println("Method Declaration Lookup EXCEPTION: " + e.toString());
        }catch(IOException e){
            System.out.println("Method Declaration Lookup EXCEPTION: " + e.toString());
        }catch(ClassNotFoundException e){
            System.out.println("Method Declaration Lookup EXCEPTION: " + e.toString());
        }
        
        return appClasses;
    }


    private static List<File> listFilesForFolder(final File folder, String extension /* e.g., ".java" */) {
        return listFilesForFolder_(folder, extension, new ArrayList<File>());
    }

    private static List<File> listFilesForFolder_(final File folder, String extension, List<File> result) {
        for (final File fileEntry : folder.listFiles()) {
            if (fileEntry.isDirectory()) {
                listFilesForFolder_(fileEntry, extension, result);
            } else {
                if (fileEntry.getName().endsWith(extension)) {
                    result.add(fileEntry);
                }
            }
        }
        return result;
    }


    /**
     * grep-like function to find package name 
     * 
     * @param f
     * @return
     * @throws FileNotFoundException
     * @throws IOException
     */
    private static String readPackageLine(File f) throws FileNotFoundException, IOException {
        try (BufferedReader reader = new BufferedReader(new FileReader(f))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("package")) {
                    break; /** found it */
                }
            }
            reader.close();
            return line;
        }
    }
    
}