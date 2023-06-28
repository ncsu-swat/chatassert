class IndexItem():
    def __init__(self, methodName, className, classPath, startLn, endLn):
        self.method_name = methodName
        self.class_name = className
        self.class_path = classPath
        self.start_ln = startLn
        self.end_ln = endLn

    def __str__(self):
        return "Class: {}\nPath: {}\nStart: {}\nEnd: {}\n------------".format(self.class_name, self.class_path, self.start_ln, self.end_ln)