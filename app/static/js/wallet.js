import {
  createPublicClient,
  createWalletClient,
  custom,
  getAddress,
  http,
  keccak256,
  toHex,
} from "https://esm.sh/viem@2";
import { avalancheFuji } from "https://esm.sh/viem@2/chains";

const root = document.body;
const expectedChain = Number(root.dataset.chainId || 43113);
const escrow = root.dataset.escrow;
const token = root.dataset.token;
const signedInWallet = root.dataset.userWallet;
const messageBox = document.querySelector("#wallet-message");
const publicClient = createPublicClient({
  chain: avalancheFuji,
  transport: http(),
});

const erc20Abi = [
  {
    type: "function", name: "approve", stateMutability: "nonpayable",
    inputs: [{name: "spender", type: "address"}, {name: "amount", type: "uint256"}],
    outputs: [{name: "", type: "bool"}],
  },
  {
    type: "function", name: "faucet", stateMutability: "nonpayable",
    inputs: [{name: "amount", type: "uint256"}], outputs: [],
  },
];

const escrowAbi = [
  {type: "error", name: "CallAlreadyExists", inputs: []},
  {type: "error", name: "CallNotFound", inputs: []},
  {type: "error", name: "InvalidCall", inputs: []},
  {type: "error", name: "InvalidPayout", inputs: []},
  {type: "error", name: "NotCallOwner", inputs: []},
  {type: "error", name: "ContributionAlreadyPaid", inputs: []},
  {type: "error", name: "RefundTooEarly", inputs: []},
  {type: "error", name: "TokenTransferMismatch", inputs: []},
  {type: "function", name: "fundCall", stateMutability: "nonpayable", inputs: [
    {name: "callId", type: "uint256"}, {name: "budget", type: "uint256"}, {name: "deadline", type: "uint64"},
  ], outputs: []},
  {type: "function", name: "pay", stateMutability: "nonpayable", inputs: [
    {name: "callId", type: "uint256"}, {name: "contributionId", type: "bytes32"},
    {name: "recipient", type: "address"}, {name: "amount", type: "uint256"},
  ], outputs: []},
];

function show(message, isError = false) {
  if (!messageBox) return;
  if (isError) {
    window.showErrorPopup?.(message);
  }
  messageBox.hidden = false;
  messageBox.textContent = message;
  messageBox.classList.toggle("error", isError);
}

async function wallet(requireLinkedMatch = true) {
  if (!window.ethereum) throw new Error("Install an EVM wallet such as Core or MetaMask.");
  const client = createWalletClient({
    chain: avalancheFuji,
    transport: custom(window.ethereum),
  });
  const [account] = await client.requestAddresses();
  const activeAccount = getAddress(account);
  if (requireLinkedMatch && signedInWallet && activeAccount !== getAddress(signedInWallet)) {
    throw new Error(
      `Core is using ${activeAccount}, but DataBounty is signed in as ${getAddress(signedInWallet)}. ` +
      "Sign out, select the funding account in Core, then connect again.",
    );
  }
  let chainId = await client.getChainId();
  if (chainId !== expectedChain) {
    show("Switching Core to Avalanche Fuji…");
    try {
      await client.switchChain({id: avalancheFuji.id});
      chainId = await client.getChainId();
    } catch (error) {
      throw new Error(
        `Reconnect Core on Avalanche Fuji (chain ${expectedChain}), then try again.`,
        {cause: error},
      );
    }
  }
  if (chainId !== avalancheFuji.id) {
    throw new Error(`Core must be connected to Avalanche Fuji (chain ${avalancheFuji.id}).`);
  }
  return {client, account: activeAccount};
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error?.message || payload.detail || "Request failed");
  return payload;
}

document.querySelector("[data-link-wallet]")?.addEventListener("click", async () => {
  try {
    show("Requesting a wallet-link signature…");
    const {client, account} = await wallet(false);
    const {message} = await postJson("/api/auth/challenge", {address: account});
    const signature = await client.signMessage({account, message});
    await postJson("/api/auth/verify", {message, signature});
    window.location.reload();
  } catch (error) { show(error.message, true); }
});

document.querySelector("[data-logout]")?.addEventListener("click", async () => {
  await postJson("/api/auth/logout", {});
  window.location.href = "/";
});

document.querySelector("[data-mint-demo-token]")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  try {
    if (!token) throw new Error("The demo token address is not configured.");
    button.disabled = true;
    const {client, account} = await wallet();
    show("Requesting valueless demo DBT from the Fuji faucet…");
    const hash = await client.writeContract({
      account,
      chain: avalancheFuji,
      address: getAddress(token),
      abi: erc20Abi,
      functionName: "faucet",
      args: [BigInt(button.dataset.amount)],
    });
    show("Waiting for the demo DBT transaction to confirm…");
    const receipt = await publicClient.waitForTransactionReceipt({hash});
    if (receipt.status !== "success") throw new Error("The demo DBT transaction failed.");
    show("Demo DBT received. You can now click Fund on Fuji.");
  } catch (error) {
    show(error.message, true);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("[data-fund-call]")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  try {
    if (!escrow || !token) throw new Error("Contract addresses are not configured.");
    button.disabled = true;
    const {client, account} = await wallet();
    const budget = BigInt(button.dataset.budget);
    show("Approving reward token…");
    const approvalHash = await client.writeContract({
      account,
      chain: avalancheFuji,
      address: getAddress(token),
      abi: erc20Abi,
      functionName: "approve",
      args: [getAddress(escrow), budget],
    });
    show("Waiting for the token approval to confirm…");
    const approvalReceipt = await publicClient.waitForTransactionReceipt({hash: approvalHash});
    if (approvalReceipt.status !== "success") throw new Error("The token approval failed.");
    const nonce = await publicClient.getTransactionCount({
      address: account,
      blockTag: "pending",
    });
    show("Submit the escrow funding transaction…");
    const hash = await client.writeContract({
      account, chain: avalancheFuji, address: getAddress(escrow), abi: escrowAbi, functionName: "fundCall",
      args: [BigInt(button.dataset.callId), budget, BigInt(button.dataset.deadline)],
      nonce,
    });
    show("Waiting for the escrow funding transaction to confirm…");
    const fundingReceipt = await publicClient.waitForTransactionReceipt({hash});
    if (fundingReceipt.status !== "success") throw new Error("The escrow funding transaction failed.");
    await postJson(button.dataset.endpoint, {tx_hash: hash});
    window.location.reload();
  } catch (error) { button.disabled = false; show(error.message, true); }
});

document.querySelector("[data-pay-contribution]")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  try {
    button.disabled = true;
    const {client, account} = await wallet();
    show("Submit the payout transaction…");
    const contributionKey = keccak256(toHex(button.dataset.contributionId));
    const hash = await client.writeContract({
      account, chain: avalancheFuji, address: getAddress(escrow), abi: escrowAbi, functionName: "pay",
      args: [BigInt(button.dataset.callId), contributionKey, getAddress(button.dataset.recipient), BigInt(button.dataset.amount)],
    });
    show("Waiting for the payout transaction to confirm…");
    const payoutReceipt = await publicClient.waitForTransactionReceipt({hash});
    if (payoutReceipt.status !== "success") throw new Error("The payout transaction failed.");
    await postJson(button.dataset.endpoint, {tx_hash: hash});
    window.location.reload();
  } catch (error) { button.disabled = false; show(error.message, true); }
});

