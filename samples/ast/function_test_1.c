#include <assert.h>

struct Point_t
{
    int x, y;
};

int a, b = 0;

int add_point(struct Point_t p)
{
    int num1 = p.x * 2;
    int num2 = p.y * 2;
    return num1 / 2 + num2 / 2;
}

void main()
{
    assert(0);
}