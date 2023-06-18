package ncsusoftware;

import py4j.GatewayServer;

public class Main {
    
    public static void main(String[] args) throws Exception {
        // uncomment to see an example of the this transformation (for canonicalization of assertion)
        // Examples.thisTransformationSampler();        
        // Examples.methodTransplantation();

        GatewayServer gatewayServer = new GatewayServer(new PY4JGateway());
        gatewayServer.start();
    }


}