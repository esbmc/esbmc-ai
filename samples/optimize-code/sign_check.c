#include <assert.h>
#include <stdbool.h>

bool is_negative(int a)
{
    return a != 0 && a < 0;
}

bool is_positive(int a)
{
    return a >= 0 && a != 0;
}

bool is_zero(int a)
{
    return a == 0;
}

int work()
{
    int a = __VERIFIER_nondet_int();

    if (is_zero(a))
    {
        return 0;
    }
    else if (is_positive(a))
    {
        return 1;
    }
    return -1;
}

int main()
{
    assert(is_negative(-1));
    assert(!is_zero(-1));
    assert(is_zero(0));
    assert(is_positive(0));
    assert(is_positive(100));
    assert(work() != 0);
    return 0;
}
