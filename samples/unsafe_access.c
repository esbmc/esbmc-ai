#include <stdlib.h>

// This program is meant to print hello world
int main()
{
    int *a = malloc(sizeof(int) * 5);
    int *b = a;
    a[0] = 0;
    free(a);
    b[0] = 1;
    free(b);
    return 0;
}
