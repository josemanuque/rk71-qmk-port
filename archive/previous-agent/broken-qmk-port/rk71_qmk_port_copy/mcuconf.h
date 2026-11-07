#pragma once

#include_next <mcuconf.h>

/* SN32F240B — enable USB peripheral */
#undef  SN32_USB_USE_USB1
#define SN32_USB_USE_USB1       TRUE
