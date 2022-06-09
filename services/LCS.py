class LCS(object):
    # this is too slow...
    def lcs(self, X, Y, m, n):
        if m == 0 or n == 0:
            return 0
        elif X[m - 1] == Y[n - 1]:
            return 1 + self.lcs(X, Y, m - 1, n - 1)
        else:
            return max(self.lcs(X, Y, m, n - 1), self.lcs(X, Y, m - 1, n))


if __name__ == "__main__":

    a = ["1", "2", 3, "123", "12345"]
    b = ["1", "2", "2,3", "123", "1111"]

    print(LCS().lcs(a, b, len(a), len(b)))
