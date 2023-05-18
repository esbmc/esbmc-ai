int foo(int n, int b[], int size)
{
    int a[n], i;
    for (i = 0; i < size + 1; i++)
    {
        a[i] = b[i];
    }
    return i;
}

int main()
{
    int i, b[100];
    for (i = 0; i < 100; i++)
    {
        b[i] = foo(i, b, i);
    }
    for (i = 0; i < 100; i++)
    {
        if (b[i] != i)
        {
        ERROR:
            return 1;
        }
    }
    return 0;
}