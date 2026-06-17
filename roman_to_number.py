def romanToInt(self, s):
        """
        :type s: str
        :rtype: int
        """
s = "LVIII"
print(len(s))
occ = 0
for i in range(len(s)):
    x = s[0]
    if s[i] == x :
        occ+1
    
        