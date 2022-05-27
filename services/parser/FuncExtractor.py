from parser.java.JavaLexer import JavaLexer
from parser.java.JavaParser import JavaParser
from parser.java.JavaParserListener import JavaParserListener

from antlr4 import CommonTokenStream, InputStream, ParseTreeWalker


class FuncExtractor(JavaParserListener):
    def __init__(self, filepath, content):
        self.filepath = filepath
        self.content = content
        self.methods = []  # used to store the methods in the file
        self.line_method_dict = (
            {}
        )  # the dictionary for line number and method relationship, key is line number; value is self.methods' index
        self.tokens = None

    def enterMethodDeclaration(self, ctx: JavaParser.MethodDeclarationContext):
        start_line = ctx.start.line
        end_line = ctx.stop.line
        start_index = ctx.start.tokenIndex
        end_index = ctx.stop.tokenIndex
        tokens = self.tokens[start_index : end_index + 1]
        tokens = [
            token.text.strip()
            for token in tokens
            if token.text.strip() != ""
            and token.type != JavaLexer.COMMENT
            and token.type != JavaLexer.LINE_COMMENT
            and token.type != JavaLexer.LPAREN
            and token.type != JavaLexer.RPAREN
            and token.type != JavaLexer.LBRACE
            and token.type != JavaLexer.RBRACE
            and token.type != JavaLexer.LBRACK
            and token.type != JavaLexer.RBRACK
        ]
        self.methods.append(
            {
                "filepath": self.filepath,
                "start": start_line,
                "end": end_line,
                "tokens": tokens,
            }
        )
        for i in range(start_line, end_line + 1):
            self.line_method_dict[i] = len(self.methods) - 1

    def parse_file(self):
        """
        parse the file and extract methods & tokenize the methods
        return:
            - List of dict {filepath, start, end, tokens}
        """
        if self.filepath.endswith(b".java"):
            input = InputStream(self.content.decode())
            lexer = JavaLexer(input)
            tokens_stream = CommonTokenStream(lexer)
            self.tokens = tokens_stream.tokens
            parser = JavaParser(tokens_stream)
            tree = parser.compilationUnit()
            walker = ParseTreeWalker()
            walker.walk(self, tree)
        else:
            pass  # Currently do not support other programming languages
        return self.methods, self.line_method_dict


if __name__ == "__main__":
    # test
    func_extractor = FuncExtractor(
        filepath="/home/zxh/programs/test/apache/ozone/hadoop-ozone/tools/src/main/java/org/apache/hadoop/ozone/admin/scm/FinalizationScmStatusSubcommand.java"
    )
    methods = func_extractor.parse_file()
    print(methods)
