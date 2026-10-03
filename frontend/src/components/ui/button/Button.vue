<script setup lang="ts">
import { cn } from '@/lib/utils'
import { buttonVariants } from '.'

interface Props {
  variant?: NonNullable<Parameters<typeof buttonVariants>[0]>['variant']
  size?: NonNullable<Parameters<typeof buttonVariants>[0]>['size']
  class?: string
}

withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'default',
})
</script>

<template>
  <button :class="cn(buttonVariants({ variant, size }), $props.class)">
    <slot />
  </button>
</template>
