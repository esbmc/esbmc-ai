#include <string.h>
#include <assert.h>

int main() {
	char* value = "branches";
	assert(strcmp("branches", value) == 0);
	return 0;
}