import { setPricesVisible, usePricesVisible } from '../prices'

export default function PriceToggle() {
  const visible = usePricesVisible()
  return (
    <button
      type="button"
      className={`chip ${visible ? 'on' : ''}`}
      aria-pressed={visible}
      onClick={() => setPricesVisible(!visible)}
    >
      Prices
    </button>
  )
}
