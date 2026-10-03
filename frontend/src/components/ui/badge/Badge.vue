<script setup lang="ts">
import { cn } from '@/lib/utils'
import { badgeVariants } from '.'

interface Props {
  variant?: NonNullable<Parameters<typeof badgeVariants>[0]>['variant']
  class?: string
}

withDefaults(defineProps<Props>(), {
  variant: 'default',
})
</script>

<template>
  <div :class="cn(badgeVariants({ variant }), $props.class)">
    <slot />
  </div>
</template>
