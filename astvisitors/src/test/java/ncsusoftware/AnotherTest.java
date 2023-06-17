package ncsusoftware;

import junit.framework.Test;
import junit.framework.TestCase;
import junit.framework.TestSuite;

/**
 * Unit test for simple App.
 */
public class AnotherTest 
    extends TestCase
{

    String somefield;

    public int someHelper() { return 0; }

    /**
     * Create the test case
     *
     * @param testName name of the test case
     */
    public AnotherTest( String testName )
    {
        super( testName );
    }

    /**
     * @return the suite of tests being tested
     */
    public static Test suite()
    {
        return new TestSuite( AppTest.class );
    }

    @org.junit.Test
    public void testApp()
    {
        /** local variables **/
        int x = 98;
        assertTrue( true );
    }
}
