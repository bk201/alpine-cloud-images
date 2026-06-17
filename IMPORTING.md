# Importing Images to Cloud Providers

At the moment, portions of this may be generalized, not detailed, and perhaps somewhat hand-wavy at times.

_**This is a Work-in-Progress**_

## Generic

Generic images, as configured here, are intended to be used on any cloud provider that is auto-detectable by Tiny Cloud or cloud-init -- _please consult the official documentation for these projects to confirm their current list of auto-detectable cloud providers._

These images should have all necessary drivers (i.e. for cloud-specific NICs) and be otherwise set up to be functional.

In order to use these `qcow2` images on AWS, Azure, GCP, or other cloud providers that do not directly support importing `qcow2` format, you will need to convert them to an image format supported by the cloud provider.

### NoCloud

NoCloud is autodetected by both Tiny Cloud and cloud-init.

### OCI

OCI is autodetected by both Tiny Cloud and cloud-init.

#### OCI Import Steps

* Upload `qcow2` file to a bucket in object storage.
* Import file as a "Custom Image" from the object storage bucket, choosing "QCOW2" as Image Type
* When importing is complete, view the details of the image and...
  * Edit Details - Select the shapes that are compatible with the image
  * Edit Image Capabilities - Select the appropriate firmware (BIOS or UEFI)

### OVH _(and possibly other OpenStack providers)_

OpenStack is currently _**only**_ autodetected by cloud-init.

### OVH Import Steps
* Download the generic **BIOS** **cloud-init** alpine version of your choice.  As of October 2025, UEFI images were not booting.  Tiny Cloud boots, but was unable to set up the SSH keys.
* Before following the steps highligted in the bellow link, make sure that:
  * You have selected the proper region as the images you upload won't be available on all regions but only on the one you select.
  * Make sure to enter the five metadata items specified in the guide (such as `image_original_user`)
  * You might have to specify `x86_64` as architecture, though I'm not sure this is necessary.
* Follow these steps https://help.ovhcloud.com/csm/en-public-cloud-compute-upload-own-image?id=kb_article_view&sysparm_article=KB0051325

#### OVH Launch Notes
* In your OVH Panel, go to `Compute->instances->create an instance`
* Select your instance model and the same region as the one you uploaded your image on
* On images, go to "Backups" tab and select your just uploaded image, select the SSH key
* Configure networking, billing, and finish.


## AWS

AWS is autodetected by both Tiny Cloud and cloud-init; however, it does not directly support QCOW2 image format.  For now, you can use a Generic image (above) but you'll need to convert it to the proper VHD format first.

The [build](build) script currently supports importing to AWS EC2 and publishing across regions (via [clouds/aws.py](clouds/aws.py)); however, this is a legacy feature, which is not done for all availalble AWS cloud regions/partitions.  A volunteer is currently covering the cost of hosting all these images.  Ideally, AWS (and other cloud providers) will someday recognize AlpineLinux as an official AMI offering from a non-profit entity, similar to Debian.

### AWS Import Steps
* upload `vhd` file to S3 bucket
* import the `vhd` as an EC2 snaphot from the S3 bucket
* register the snapshot as an AMI
* AMIs can be copied to other regions

## Azure

Azure is autodetected by both Tiny Cloud and cloud-init; however, it does not directly support QCOW2 image format.  For now, you can use a Generic image (above) but you'll need to convert it to the proper VHD format first.

### Azure Import Steps
* upload `vhd` to an Azure storage container (`vhd`'s default to "page blob")
* create/select an Azure Compute Gallery
* create/select a VM Image Definition
  * (usually based on the `vhd` name, without version info, i.e. `alpine-x86_64-uefi-tiny`)
  * Linux OS
  * "Gen 2" for UEFI, "Gen 1" for BIOS
  * √ higher storage performance with NVMe
  * √ accelerated networking
  * VM architecture, "x64" or "arm"
  * OS state "generalized"
* create a VM Image Version
  * Version number must be #.#.# (i.e. 3.21.0) -- does not support `-r1` etc.
  * Source "Storage blobs (VHDs)"
  * OS Source: browse to what you uploaded to the `.vhd` in the storage container

### Azure Launch Notes
* create VM from the image gallery version
* security type "Standard"
* Username "alpine"
* SSH public key source
  * "Use existing..." and paste your key's "`.pub`" contents in SSH public key box.
  * other options may also work
* License Type "Other"
* "Disks" tab...
* √ delete with VM
* "Networking" tab...
* √ delete public IP and NIC when VM deleted
* "Advanced" tab...
* √ Enable User Data (for Tiny Cloud or cloud-init)
* enter User Data payload
* "Review + Create" tab...
* Create

_**NOTE** Provisioning Tiny Cloud will "time out", but the instance is actually created and fully operational.  Current theory is that Azure Compute is waiting to hear some kind of signal back from the instance which Tiny Cloud is currently not sending._

## GCP

GCP is autodetected by both Tiny Cloud and cloud-init; however, it does not directly support QCOW2 image format.  For now, you can use a Generic image (above) but you'll need to convert it to the proper "raw.tar.gz" format first.

### GCP Import Steps
I was unable to import a working image via Google Cloud web UI, but here's what worked with the `gcloud` CLI...
```
gcloud auth login

gcloud storage cp <alpine-raw.tar.gz-file> gs://<cloud-storage-bucket>

gcloud compute images create <image-name> \
  --source-uri gs://<cloud-storage-bucket>/<alpine-raw.tar.gz-file> \
  --architecture {ARM64|X86_64}
  --guest-os-features GVNIC,VIRTIO_SCSI_MULTIQUEUE[,UEFI_COMPATIBLE]
```
...once imported, the Google Cloud web UI can be used to launch instances.

### GCP Launch Notes
When creating an instance and pasting an SSH public key, Google Cloud will use the comment field to determine what login it belongs to.

To ensure that a SSH key is associated with the `alpine` user, make sure it appears in the public key's comment field...
```
ssh-ed25519 AAAAC3NZAc1Lzdi1nte5aaaaiosu2eyCQfB/uBziBPPmn9fa7G9G+nf0lGXQxypWMjgP alpine
```
