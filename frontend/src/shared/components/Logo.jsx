import logo from "../../assets/logo.png";

export default function Logo() {
  return (
    <img
      src={logo}
      alt="Mabit logo"
      className="h-full w-auto select-none"
      draggable={false}
    />
  );
}
