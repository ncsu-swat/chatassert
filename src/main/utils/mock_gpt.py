import random

mock_data = [
    {
        "testName": "testToMillibar",
        "oracles": [
            "assertEquals(expected, actual);",
            "assertTrue(expected.equals(actual));",
            "assertNotNull(actual);",
            "assertNotSame(expected, actual);",
            "assertEquals(expected, actual);",
            "assertFalse(!expected.equals(actual));",
            "assertEquals(expected, actual);",
            "assertNotSame(expected, actual);",
            "assertNotNull(actual);",
            "assertTrue(expected.equals(actual));"
        ]
    },
    {
        "testName": "testReadExcel",
        "oracles": [
            "assertNotNull(aXls);",
            "assertTrue(aXls.exists());",
            "assertEquals(2, 1+1);",
            "assertNotEquals(\"Hello\", \"World\");",
            "assertFalse(1 > 2);",
            "assertNull(null);",
            "assertThrows(Exception.class, () -> { // code that throws an exception });",
            "assertNotSame(\"Hello\", new String(\"Hello\"));",
            "assertSame(\"Hello\", \"Hello\");",
            "assertArrayEquals(new int[]{1, 2, 3}, new int[]{1, 2, 3});"
        ]
    }
]

def mock_response(test_name):
    print('\nMOCKING - {}\n'.format(test_name))

    for data in mock_data:
        if data["testName"] == test_name:
            return data["oracles"][random.randint(0, len(data["oracles"])-1)]
    
    print("This test is not included in the mock")

    return None