# Alpine Cloud Images Packer Configuration

packer {
  required_plugins {
    qemu = {
      source  = "github.com/hashicorp/qemu"
      version = "~> 1"
    }
  }
}

### Variables

# include debug output from provisioning/post-processing scripts
variable "DEBUG" {
  default = 0
}
# indicates cloud_helper.py should be run with --use-broker
variable "USE_BROKER" {
  default = 0
}
# regions to skip publishing
variable "NOT_REGIONS" {
  default = null
}

# tuneable QEMU VM parameters, based on perfomance of the local machine;
# overrideable via build script --vars parameter referencing a Packer
# ".vars.hcl" file containing alternate settings
variable "qemu" {
  default = {
    boot_wait = {
      aarch64 = "1m"
      x86_64  = "1m"
    }
    cmd_wait    = "5s"
    ssh_timeout = "1m"
    memory      = 1024 # MiB
  }
}

### Local Data

locals {
  # possible actions for the post-processor
  actions = [
    "local", "upload", "import", "sign", "publish", "release"
  ]

  debug_arg       = var.DEBUG == 0 ? "" : "--debug"
  broker_arg      = var.USE_BROKER == 0 ? "" : "--use-broker"
  not-regions_arg = var.NOT_REGIONS == null ? "" : "--not-regions ${var.NOT_REGIONS}"

  qemu_append_modules = "loop,squashfs,sd-mod,usb-storage,virtio_net,virtio_pci,virtio_blk,ext4,fat,vfat,nls_cp437,nls_iso8859-1,nls_utf8"
  qemu_console = {
    aarch64 = "ttyAMA0"
    x86_64  = "ttyS0"
  }

  # resolve actionable build configs
  configs = { for b, cfg in yamldecode(file("work/images.yaml")) :
    b => cfg if contains(keys(cfg), "actions")
  }
}

### Build Sources

# Don't build
source null alpine {
  communicator = "none"
}

# Common to all QEMU builds
source qemu alpine {
  # qemu machine
  headless       = true
  memory         = var.qemu.memory
  net_device     = "virtio-net"
  disk_interface = "virtio"

  # build environment
  boot_command         = []
  http_directory       = "work/apkovl"
  ssh_username         = "root"
  ssh_private_key_file = "work/ssh/packer_ed25519"
  ssh_timeout          = var.qemu.ssh_timeout
  shutdown_command     = "poweroff"
}

build {
  name = "alpine"

  ## Builders

  # QEMU builder
  dynamic "source" {
    for_each = { for b, c in local.configs :
      b => c if contains(c.actions, "local")
    }
    iterator = B
    labels   = ["qemu.alpine"] # links us to the base source

    content {
      name = B.key

      # qemu machine
      qemu_binary = "qemu-system-${B.value.arch}"
      qemuargs = concat(
        coalesce(B.value.qemu.args, []),
        [
          ["-kernel", "work/boot/latest-${B.value.arch}/vmlinuz-virt"],
          ["-initrd", "work/boot/latest-${B.value.arch}/initramfs-virt"],
          [
            "-append",
            "modules=${local.qemu_append_modules} console=${local.qemu_console[B.value.arch]} ip=dhcp apkovl=http://{{ .HTTPIP }}:{{ .HTTPPort }}/packer.apkovl.tar.gz"
          ],
        ],
      )
      machine_type = B.value.qemu.machine_type
      firmware     = B.value.qemu.firmware

      # build environment
      iso_url      = "work/boot/latest-${B.value.arch}/alpine-virt.iso"
      iso_checksum = "file:work/boot/latest-${B.value.arch}/alpine-virt.iso.sha512"
      boot_wait    = var.qemu.boot_wait[B.value.arch]

      # results
      output_directory = "work/images/${B.value.cloud}/${B.value.image_key}"
      disk_size        = B.value.disk_size
      format           = "qcow2"
      vm_name          = "image.qcow2"
    }
  }

  # Null builder (don't build, but we might do other actions)
  dynamic "source" {
    for_each = { for b, c in local.configs :
      b => c if !contains(c.actions, "local")
    }
    iterator = B
    labels   = ["null.alpine"]
    content {
      name = B.key
    }
  }

  ## build provisioners

  # install setup files
  dynamic "provisioner" {
    for_each = { for b, c in local.configs :
      b => c if contains(c.actions, "local")
    }
    iterator = B
    labels   = ["file"]
    content {
      only = ["qemu.${B.key}"] # configs specific to one build

      sources     = [for d in B.value.script_dirs : "work/scripts/${d}"]
      destination = "/tmp/"
    }
  }

  # run setup scripts
  dynamic "provisioner" {
    for_each = { for b, c in local.configs :
      b => c if contains(c.actions, "local")
    }
    iterator = B
    labels   = ["shell"]
    content {
      only = ["qemu.${B.key}"] # configs specific to one build

      scripts          = [for s in B.value.scripts : "work/scripts/${s}"]
      use_env_var_file = true
      environment_vars = [
        "DEBUG=${var.DEBUG}",
        "ARCH=${B.value.arch}",
        "BOOTLOADER=${B.value.bootloader}",
        "BOOTLOADER_TIMEOUT=${B.value.bootloader_timeout}",
        "BOOTSTRAP=${B.value.bootstrap}",
        "BUILD_NAME=${B.value.name}",
        "BUILD_REVISION=${B.value.revision}",
        "CLOUD=${B.value.cloud}",
        "END_OF_LIFE=${B.value.end_of_life}",
        "FIRMWARE=${B.value.firmware}",
        "IMAGE_LOGIN=${B.value.login}",
        "INITFS_FEATURES=${B.value.initfs_features}",
        "KERNEL_MODULES=${B.value.kernel_modules}",
        "KERNEL_OPTIONS=${B.value.kernel_options}",
        "MOTD=${B.value.motd}",
        "NTP_SERVER=${B.value.ntp_server}",
        "PACKAGES_ADD=${B.value.packages.add}",
        "PACKAGES_DEL=${B.value.packages.del}",
        "PACKAGES_NOSCRIPTS=${B.value.packages.noscripts}",
        "RELEASE=${B.value.release}",
        "REPOS=${B.value.repos}",
        "REPO_KEYS=${B.value.repo_keys}",
        "SERVICES_ENABLE=${B.value.services.enable}",
        "SERVICES_DISABLE=${B.value.services.disable}",
        "VERSION=${B.value.version}",
      ]
    }
  }

  ## build post-processor

  # import and/or publish cloud images
  dynamic "post-processor" {
    for_each = { for b, c in local.configs :
      b => c if length(setintersection(c.actions, local.actions)) > 0
    }
    iterator = B
    labels   = ["shell-local"]
    content {
      only = ["qemu.${B.key}", "null.${B.key}"]
      inline = [for action in local.actions :
        "./cloud_helper.py ${action} ${local.debug_arg} ${local.broker_arg} ${local.not-regions_arg} ${B.key}" if contains(B.value.actions, action)
      ]
    }
  }
}
