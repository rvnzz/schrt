<script setup lang="ts">
import { SelectValue, useForwardProps } from 'radix-vue'

const props = defineProps<{ class?: string }>()
const forwarded = useForwardProps(props)
</script>

<template>
  <SelectValue v-bind="forwarded">
    <slot />
  </SelectValue>
</template>
