import { ErrorResult } from '@/components/ErrorResult'

export default function Forbidden() {
  return <ErrorResult kind="403" />
}
