#include <iostream>

#include "arp_message.hh"
#include "ethernet_frame.hh"
#include "exception.hh"
#include "helpers.hh"
#include "network_interface.hh"

using namespace std;

//! \param[in] ethernet_address Ethernet (what ARP calls "hardware") address of the interface
//! \param[in] ip_address IP (what ARP calls "protocol") address of the interface
NetworkInterface::NetworkInterface( string_view name,
                                    shared_ptr<OutputPort> port,
                                    const EthernetAddress& ethernet_address,
                                    const Address& ip_address )
  : name_( name )
  , port_( notnull( "OutputPort", move( port ) ) )
  , ethernet_address_( ethernet_address )
  , ip_address_( ip_address )
{
  cerr << "DEBUG: Network interface has Ethernet address " << to_string( ethernet_address_ ) << " and IP address "
       << ip_address.ip() << "\n";
}

//! \param[in] dgram the IPv4 datagram to be sent
//! \param[in] next_hop the IP address of the interface to send it to (typically a router or default gateway, but
//! may also be another host if directly connected to the same network as the destination) Note: the Address type
//! can be converted to a uint32_t (raw 32-bit IP address) by using the Address::ipv4_numeric() method.
void NetworkInterface::send_datagram( InternetDatagram dgram, const Address& next_hop )
{
  const uint32_t ip = next_hop.ipv4_numeric();
  const auto mapping = mappings_.find( ip );
  if ( mapping != mappings_.end() ) {
    send_ipv4( dgram, mapping->second.ethernet_address );
    return;
  }

  auto [request, inserted] = pending_.try_emplace( ip );
  request->second.datagrams.push( move( dgram ) );
  if ( inserted ) {
    send_arp( ARPMessage::OPCODE_REQUEST, {}, ip );
  }
}

//! \param[in] frame the incoming Ethernet frame
void NetworkInterface::recv_frame( EthernetFrame frame )
{
  if ( frame.header.dst != ethernet_address_ and frame.header.dst != ETHERNET_BROADCAST ) {
    return;
  }
  if ( frame.header.type == EthernetHeader::TYPE_IPv4 ) {
    InternetDatagram dgram;
    if ( parse( dgram, move( frame.payload ) ) ) {
      datagrams_received_.push( move( dgram ) );
    }
    return;
  }
  if ( frame.header.type != EthernetHeader::TYPE_ARP ) {
    return;
  }

  ARPMessage arp;
  if ( not parse( arp, frame.payload ) ) {
    return;
  }
  mappings_.insert_or_assign( arp.sender_ip_address, Mapping { .ethernet_address = arp.sender_ethernet_address } );
  if ( arp.opcode == ARPMessage::OPCODE_REQUEST and arp.target_ip_address == ip_address_.ipv4_numeric() ) {
    send_arp( ARPMessage::OPCODE_REPLY, arp.sender_ethernet_address, arp.sender_ip_address );
  }

  const auto request = pending_.find( arp.sender_ip_address );
  if ( request != pending_.end() ) {
    // Detach the queue before transmitting: the output port can call back into an interface.
    auto datagrams = move( request->second.datagrams );
    pending_.erase( request );
    while ( not datagrams.empty() ) {
      send_ipv4( datagrams.front(), arp.sender_ethernet_address );
      datagrams.pop();
    }
  }
}

//! \param[in] ms_since_last_tick the number of milliseconds since the last call to this method
void NetworkInterface::tick( const size_t ms_since_last_tick )
{
  const auto expire = [ms_since_last_tick]( auto& entries ) {
    for ( auto entry = entries.begin(); entry != entries.end(); ) {
      if ( ms_since_last_tick >= entry->second.remaining_ms ) {
        entry = entries.erase( entry );
      } else {
        entry->second.remaining_ms -= ms_since_last_tick;
        ++entry;
      }
    }
  };
  expire( mappings_ );
  expire( pending_ ); // Expiring a request also discards all datagrams waiting on it.
}

void NetworkInterface::send_ipv4( const InternetDatagram& dgram, const EthernetAddress& destination )
{
  EthernetFrame frame;
  frame.header = { .dst = destination, .src = ethernet_address_, .type = EthernetHeader::TYPE_IPv4 };
  frame.payload = serialize( dgram );
  transmit( frame );
}

void NetworkInterface::send_arp( uint16_t opcode, const EthernetAddress& target_ethernet, uint32_t target_ip )
{
  ARPMessage arp;
  arp.opcode = opcode;
  arp.sender_ethernet_address = ethernet_address_;
  arp.sender_ip_address = ip_address_.ipv4_numeric();
  arp.target_ethernet_address = target_ethernet;
  arp.target_ip_address = target_ip;

  EthernetFrame frame;
  frame.header = { .dst = opcode == ARPMessage::OPCODE_REQUEST ? ETHERNET_BROADCAST : target_ethernet,
                   .src = ethernet_address_,
                   .type = EthernetHeader::TYPE_ARP };
  frame.payload = serialize( arp );
  transmit( frame );
}
