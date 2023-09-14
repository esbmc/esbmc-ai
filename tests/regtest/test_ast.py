source_code = """struct linear
{
    int value;
};

typedef struct linear LinearTypeDef;

typedef struct
{
    int x;
    int y;
} Point;

Point a;
Point *b;

int c;

char *d;

typedef enum Types
{
    ONE,
    TWO,
    THREE
} Typest;

enum Types e = ONE;

Typest f = TWO;

union Combines
{
    int a;
    int b;
    int c;
};

typedef union Combines CombinesTypeDef;

enum extra { A, B, C};

typedef enum extra ExtraEnum;"""
# TODO
