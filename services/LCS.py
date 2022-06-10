class LCS(object):
    def lcs(self, s1, s2):

        # let s1 be the shortest string
        if len(s1) > len(s2):
            s1, s2 = s2, s1
        equal = {}

        # particular cases
        if len(s1) == 0:
            return 0

        # first preprocessing step: computation of the equality points
        for i in range(0, len(s2)):
            equal[i + 1] = self.list_of_indices(s2[i], s1)[::-1]

        # second preprocessing step: similarity threshold table
        threshold = [len(s1) + 1 for _ in range(0, len(s2) + 1)]
        threshold[0] = 0
        # processing step: algorithm proper
        for i in range(0, len(s2)):
            for j in equal[i + 1]:
                k = self.look_for_threshold_index(
                    j, threshold
                )  # look for k such that threshold[k-1] < j <= threshold[k]:
                if j < threshold[k]:
                    threshold[k] = j

        # postprocessing step: looking for the result, i.e., the similarity between the two strings
        # it is the first index in threshold with a value different from len(s1) + 1, starting from the right
        result = 0
        for k in range(len(s2), 0, -1):
            if len(s1) + 1 != threshold[k]:
                result = k
                break
        return result

    def list_of_indices(self, c, s):
        """
        Returns the list of indices of the occurrences of c in s
        """
        result = []
        i = 0
        while i < len(s):
            if type(s) == list:
                try:
                    i = s[i:].index(c) + i + 1
                except ValueError:
                    i = 0
            else:
                i = s.find(c, i) + 1

            if 0 != i:
                result.append(i - 1)
            else:
                break
        return result

    def look_for_threshold_index(self, j, threshold, left=None, right=None):

        if (None, None) == (left, right):
            left, right = 0, len(threshold) - 1

        if left > right:
            raise ValueError("Value in left higher than right")
        elif left + 1 == right or left == right:
            return right
        else:
            mid = int((left + right) / 2)
            if j <= threshold[mid]:
                left, right = left, mid
            else:
                left, right = mid, right
            return self.look_for_threshold_index(j, threshold, left, right)


if __name__ == "__main__":

    a = ["1", "2", 3, "123", "12345"]
    b = ["1", "2", "2,3", "123", "1111"]

    print(LCS().lcs(a, b))
