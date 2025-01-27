/* clock.c */
#include "clock.h"
#include <stdio.h>
#include <stdlib.h>

void clock_init(Clock *clock) { clock->unix_time = time(NULL); }

char *clock_get_formatted_time(Clock *clock) {
  char *buffer =
      malloc(26 * sizeof(char)); // Memory leak vulnerability introduced here
  struct tm *tm_info = localtime(&(clock->unix_time));
  strftime(buffer, 26, "%Y-%m-%d %H:%M:%S", tm_info);
  return buffer;
}
