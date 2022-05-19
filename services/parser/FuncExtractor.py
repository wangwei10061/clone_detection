from antlr4 import CommonTokenStream, FileStream, ParseTreeWalker
from java.JavaLexer import JavaLexer
from java.JavaParser import JavaParser
from java.JavaParserListener import JavaParserListener


class FuncExtractor(JavaParserListener):
    def __init__(self, filepath):
        self.filepath = filepath
        self.methods = []  # used to store the methods in the file
        self.tokens = None

    def enterMethodDeclaration(self, ctx: JavaParser.MethodDeclarationContext):
        start_line = ctx.start.line
        end_line = ctx.stop.line
        start_index = ctx.start.tokenIndex
        end_index = ctx.stop.tokenIndex
        tokens = self.tokens[start_index : end_index + 1]
        tokens = [
            token.text.strip() for token in tokens if token.text.strip() != ""
        ]
        self.methods.append(
            {
                "filepath": self.filepath,
                "start": start_line,
                "end": end_line,
                "tokens": tokens,
            }
        )

    def parse_file(self):
        """
        parse the file and extract methods & tokenize the methods
        return:
            - List of dict {filepath, start, end, tokens}
        """
        input = FileStream(self.filepath)
        lexer = JavaLexer(input)
        tokens_stream = CommonTokenStream(lexer)
        self.tokens = tokens_stream.tokens
        parser = JavaParser(tokens_stream)
        tree = parser.compilationUnit()
        walker = ParseTreeWalker()
        walker.walk(self, tree)
        return self.methods


if __name__ == "__main__":
    # test
    func_extractor = FuncExtractor(
        filepath="/home/zxh/programs/test/apache/ozone/hadoop-ozone/tools/src/main/java/org/apache/hadoop/ozone/admin/scm/FinalizationScmStatusSubcommand.java"
    )
    methods = func_extractor.parse_file()
    print(methods)
