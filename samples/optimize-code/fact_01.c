#include <stdio.h>

int factorial(int n)
{
    if (n <= 0)
    {
        return 1;
    }
    else
    {
        int result = 1;
        while (n > 0)
        {
            result *= n;
            n--;
        }
        return result;
    }
}

int main()
{
    int num = 10;
    printf("Factorial of %d is %d\n", num, factorial(num));
    return 0;
}
