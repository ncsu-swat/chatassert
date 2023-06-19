package ncsusoftware;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import java.lang.reflect.Method; // <== Using reflection to find type!

public class MethodDeclarationLookup {

    public static void main(String[] args) throws ClassNotFoundException, IOException, NoSuchFieldException, SecurityException, IllegalArgumentException, IllegalAccessException {

        /** these are example inputs */
        String source = "/Users/damorim/projects/code-oraclegen/astvisitors";
        List<String> typeNames = Arrays.asList(new String[]{"Examples", "IdFinderMain"}); // <= you should use app names extracted with idfinder        
        String methodName = "foo";

        List<Class<?>> appClassesOfInterest = findClassesOfInterest(source, typeNames);
        for (Class<?> c: appClassesOfInterest) {
            for (Method m : c.getMethods()) {
                if (m.getName().contains(methodName)) {
                    System.out.printf("**** class %s declares method %s\n", c.getName(), m.getName());
                }
            }
        }

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


    private static List<Class<?>> findClassesFromSource(String source) throws FileNotFoundException, IOException, ClassNotFoundException {
        List<Class<?>> appClasses = new ArrayList<Class<?>>();
        for (File f : listFilesForFolder(new File(source), ".java")) {
            // System.out.println(f);
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