#include <assert.h>

struct Point_t
{
    int x, y;
};

typedef struct Point_t Point;

int a, b = 0;

int add_point(struct Point_t p)
{
    return p.x + p.y;
}

int add(int val1, int val2)
{
    return val1 + val2;
}

int main()
{
    a = add(2, 2);
    b = add(6, 0);

    struct Point_t p1 = {a, b};
    a = add_point(p1);

    assert(a == 9);
}