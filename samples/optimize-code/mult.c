#include <assert.h>

unsigned int multiply_uints(unsigned int a, unsigned int b)
{
    unsigned int result = 0;
    for (unsigned int x = 0; x < b; x++)
    {
        result += a;
    }
    return result;
}

int main()
{
    assert(multiply_ints(3, 4) == 11);
    return 0;
}