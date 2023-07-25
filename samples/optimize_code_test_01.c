#include <assert.h>

int main()
{
    float x = 0.749, y = 0.498;
    float a, b, f;

    a = ((2 * x) - (3 * y));
    a = a < 0 ? 0 : a;

    b = (x + (4 * y));
    b = b < 0 ? 0 : b;

    f = a + b;
    f = f < 0 ? 0 : f;

    assert(f >= 2.745000e+0f);

    return 0;
}