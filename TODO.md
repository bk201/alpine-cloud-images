# TODO

## SOON-ish

* do we still need to put `interfaces` into the image, or will Tiny Cloud and
  cloud-init handle it?  _(seems to be so, but need to test)_

* `generic` cloud should result in multiple formats -- implement
  `image_formats` array/map in parallel (or instead of `image_format`, etc.)

* check free space at upload location

* if we're going to (or past) the `sign` step, can we pre-auth the signer (keybase, gpg)?

* detect and use GNU `tar` -- busybox and BSD variants can't be used to create GCP images

## LATER

* support `<` and `>` in `EXCLUDE` and `WHEN` blocks for version comparison

* stop making BIOS images by default (or entirely?)
  * switch to UEFI only ***OR***...
  * ...figure out how to do hybrid BIOS/UEFI images

* figure out rollback / `refresh_state()` for images that are already signed,
  don't sign again unless directed to do so.
