
/* timer.h */
#ifndef TIMER_H
#define TIMER_H

#include "clock.h"

void timer_tick(Clock *clock, int seconds, int tick_rate);

#endif // TIMER_H