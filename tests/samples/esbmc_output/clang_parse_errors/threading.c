ESBMC version 7.5.0 64-bit x86_64 linux
Target: 64-bit little-endian x86_64-unknown-linux with esbmclibc
Parsing ./temp/threading.c
In file included from ./temp/threading.c:23:
In file included from /usr/include/stdio.h:36:
In file included from /tmp/esbmc.20e5-e0f3-d837/headers/stdarg.h:4:
/tmp/esbmc-headers-5458-a31d-5077/stdarg.h:14:1: error: expected expression
typedef __builtin_va_list va_list;
^
./temp/threading.c:26:12: error: function definition is not allowed here
int main() {
           ^
ERROR: PARSING ERROR
