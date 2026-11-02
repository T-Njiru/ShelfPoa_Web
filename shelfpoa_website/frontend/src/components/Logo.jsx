import logo from "../assets/logo-shelfpoa.png";

// Official ShelfPoa mark + wordmark. White lettering on a transparent background,
// so it needs a dark or orange surface behind it. Size it with `className` (set the height).
export function Logo({ className = "h-8" }) {
  return <img src={logo} alt="ShelfPoa" className={`${className} w-auto self-start shrink-0 block select-none`} draggable={false} />;
}
